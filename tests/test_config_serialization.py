"""Regression tests for dynamically defined configuration serialization."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


def _run(script: str, directory: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", dedent(script)],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_dynamic_configs_round_trip_in_fresh_interpreter(tmp_path: Path) -> None:
    """Data and validators survive transfer without copying ambient activation."""
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

        assert Config.model_config["use_attribute_docstrings"] is True

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
    )


def test_local_context_transfers_through_loky(tmp_path: Path) -> None:
    """Local context classes work across worker processes."""
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
    )


@pytest.mark.parametrize("from_instance", [False, True])
def test_generated_factories_round_trip(tmp_path: Path, from_instance: bool) -> None:
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
        assert Config.model_config["use_attribute_docstrings"] is True
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
    _run(producer, tmp_path)
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
    _run(consumer, tmp_path)


def test_recursive_factory_serialization_and_loky_transfer(tmp_path: Path) -> None:
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
    )


def test_hashable_mutable_factory_defaults_transfer(tmp_path: Path) -> None:
    """Copy-default wrappers and templates survive fresh-process cloudpickle."""
    _run(
        """
        from pathlib import Path
        from typing import Any
        import cloudpickle
        from confidantic import Factory

        class Values(list):
            __hash__ = object.__hash__

        class Target:
            def __init__(self, items: Any = Values([1])) -> None:
                self.items = items

        Path("copied.pkl").write_bytes(cloudpickle.dumps(Factory.model_from(Target)))
        """,
        tmp_path,
    )
    _run(
        """
        from pathlib import Path
        import cloudpickle

        model = cloudpickle.loads(Path("copied.pkl").read_bytes())
        first, second = model(), model()
        first.items.append(2)
        assert second.items == [1]
        assert model().model_resolve().items == [1]
        """,
        tmp_path,
    )


def test_unavailable_module_preserves_descriptions_with_extraction(
    tmp_path: Path,
) -> None:
    """Local classes retain descriptions when their module is unavailable."""
    producer = tmp_path / "producer"
    consumer = tmp_path / "consumer"
    producer.mkdir()
    consumer.mkdir()
    (producer / "model_defs.py").write_text(
        "from confidantic import BaseConfig, ConfigModelDict\n"
        "from pydantic import Field\n"
        "def make_model():\n"
        "    class Parent(BaseConfig):\n"
        "        model_config = ConfigModelDict(use_attribute_docstrings=True)\n"
        "    class Config(Parent):\n"
        "        value: int = Field(7, description='Explicit description')\n"
        "        documented: int = 8\n"
        '        """Extracted description."""\n'
        "    return Config\n"
    )
    _run(
        """
        from pathlib import Path
        import cloudpickle
        from model_defs import make_model
        config = make_model()()
        assert config.model_config["use_attribute_docstrings"] is True
        assert type(config).model_fields["documented"].description == "Extracted description."
        Path("../consumer/payload.pkl").write_bytes(cloudpickle.dumps(config))
        """,
        producer,
    )
    _run(
        """
        from importlib.util import find_spec
        from pathlib import Path
        import cloudpickle
        assert find_spec("model_defs") is None
        config = cloudpickle.loads(Path("payload.pkl").read_bytes())
        assert config.value == 7
        assert config.documented == 8
        assert type(config).model_fields["value"].description == "Explicit description"
        assert type(config).model_fields["documented"].description == "Extracted description."
        """,
        consumer,
    )
