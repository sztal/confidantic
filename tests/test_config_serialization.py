"""Regression tests for dynamically defined configuration serialization."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.fixture
def worker_environment() -> dict[str, str]:
    """Disable source inspection before either interpreter imports Confidantic."""
    return {**os.environ, "CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS": "false"}


def _run(script: str, directory: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-c", dedent(script)],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("docstrings", ["true", "false"])
def test_dynamic_configs_round_trip_in_fresh_interpreter(
    tmp_path: Path, worker_environment: dict[str, str], docstrings: str
) -> None:
    """Data and validators survive transfer without copying ambient activation."""
    worker_environment["CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS"] = docstrings
    _run(
        """
        from pathlib import Path
        import cloudpickle
        from pydantic import BaseModel, Field
        from confidantic import BaseConfig
        from confidantic.context import BaseContext

        class Nested(BaseModel):
            x: int = 1
            y: int = 2

        class Config(BaseConfig):
            seed: int = 7
            nested: Nested = Field(default_factory=lambda data: Nested(y=data["seed"]))

        class Active(BaseContext):
            value: int = 1

        class Child(Active):
            pass

        baseline = Active.set(Active(value=99))
        Child.set(Child(value=88))
        config = Config(nested={"x": 4})
        assert config.nested.y == 7
        payload = (config, Active(value=2), Child(value=3), lambda: Active.current().value)
        blob = cloudpickle.dumps(payload)
        restored = cloudpickle.loads(blob)
        assert type(restored[0]) is Config
        assert restored[0].model_field_sources == config.model_field_sources
        assert restored[3]() == 99
        assert Active.current() is baseline
        Path("payload.pkl").write_bytes(blob)
        """,
        tmp_path,
        worker_environment,
    )
    _run(
        """
        from pathlib import Path
        import cloudpickle
        config, active, child, callback = cloudpickle.loads(Path("payload.pkl").read_bytes())
        assert active.value == 2 and child.value == 3
        assert type(active).current().value == 1
        assert type(child).current().value == 1
        assert callback() == 1
        assert config.nested.x == 4 and config.nested.y == 7
        updated = type(config)(seed=9, nested={"x": 8})
        assert updated.nested.x == 8 and updated.nested.y == 9
        assert config.model_field_sources["nested"][1] is type(config)
        """,
        tmp_path,
        worker_environment,
    )


def test_local_context_transfers_through_loky(
    tmp_path: Path, worker_environment: dict[str, str]
) -> None:
    """Local context classes work when source inspection is disabled at import."""
    _run(
        """
        from joblib import Parallel, delayed
        from confidantic.context import BaseContext

        def run():
            class Local(BaseContext):
                value: int = 1

            Local.set(Local(value=99))

            def task(instance):
                assert Local.current().value == 1
                return instance.value

            assert Parallel(n_jobs=2)(
                delayed(task)(Local(value=i)) for i in range(3)
            ) == [0, 1, 2]
            assert Local.current().value == 99

        run()
        """,
        tmp_path,
        worker_environment,
    )


@pytest.mark.parametrize("from_instance", [False, True])
def test_generated_factories_round_trip(
    tmp_path: Path, worker_environment: dict[str, str], from_instance: bool
) -> None:
    """Factory classes, defaults, and typed fields survive fresh-process loading."""
    producer = """
        from pathlib import Path
        from typing import Any
        import cloudpickle
        from confidantic import BaseConfig, Factory

        class Payload:
            __hash__ = None

            def __init__(self, value: int = 5):
                self.value = value

        class Target:
            def __init__(self, value: int = 3, items: list[int] = [1], payload: Any = Payload()):
                self.value = value
                self.items = items
                self.payload = payload

        source = Target(value=6, items=[2], payload=Payload(8)) if FROM_INSTANCE else Target
        Config = Factory.model_from(source)
        class Container(BaseConfig):
            target: Factory[Target]

        first, second = Config(), Config()
        first.items.append(99)
        first.payload.value = 99
        assert second.items == ([2] if FROM_INSTANCE else [1])
        assert second.payload.value == (8 if FROM_INSTANCE else 5)
        objects = (Config, Config(value=7), Container(target={"value": 8}), Factory[Target])
        blob = cloudpickle.dumps(objects)
        restored = cloudpickle.loads(blob)
        assert restored[0] is Config
        assert restored[1].model_resolve().value == 7
        assert restored[2].model_resolve().target.value == 8
        Path("factory.pkl").write_bytes(blob)
    """.replace("FROM_INSTANCE", repr(from_instance))
    _run(producer, tmp_path, worker_environment)
    consumer = """
        from pathlib import Path
        import cloudpickle
        Config, instance, container, specialized = cloudpickle.loads(Path("factory.pkl").read_bytes())
        assert issubclass(Config, specialized)
        assert type(instance) is Config
        assert instance.model_resolve().value == 7
        assert Config(value=9).model_resolve().value == 9
        assert container.model_resolve().target.value == 8
        assert type(container)(target={"value": 11}).model_resolve().target.value == 11
        first, second = Config(), Config()
        assert first.value == (6 if FROM_INSTANCE else 3)
        assert first.items == ([2] if FROM_INSTANCE else [1])
        assert first.payload.value == (8 if FROM_INSTANCE else 5)
        assert type(first.payload) is type(second.payload)
        first.items.append(99)
        first.payload.value = 99
        assert second.items == ([2] if FROM_INSTANCE else [1])
        assert second.payload.value == (8 if FROM_INSTANCE else 5)
    """.replace("FROM_INSTANCE", repr(from_instance))
    _run(consumer, tmp_path, worker_environment)


def test_recursive_factory_serialization_and_loky_transfer(
    tmp_path: Path, worker_environment: dict[str, str]
) -> None:
    """Recursive factory defaults remain usable and isolated across processes."""
    _run(
        """
        from pathlib import Path
        import cloudpickle
        from joblib import Parallel, delayed
        from confidantic import Factory

        class Child:
            def __init__(self, items: list[int] = [1]):
                self.items = items

        class Parent:
            def __init__(self, child: Child = Child()):
                self.child = child

        Config = Factory.model_from(Parent, __recursive__=Child)
        blob = cloudpickle.dumps((Config, Config()))
        restored_type, restored = cloudpickle.loads(blob)
        assert restored_type is Config
        assert restored.model_resolve().child.items == [1]
        assert Parallel(n_jobs=2)(
            delayed(lambda config: config.model_resolve().child.items)(Config())
            for _ in range(2)
        ) == [[1], [1]]
        Path("recursive.pkl").write_bytes(blob)
        """,
        tmp_path,
        worker_environment,
    )
    _run(
        """
        from pathlib import Path
        import cloudpickle
        Config, instance = cloudpickle.loads(Path("recursive.pkl").read_bytes())
        assert instance.model_resolve().child.items == [1]
        first, second = Config(), Config()
        first.child.items.append(2)
        assert first.model_resolve().child.items == [1, 2]
        assert second.model_resolve().child.items == [1]
        """,
        tmp_path,
        worker_environment,
    )
