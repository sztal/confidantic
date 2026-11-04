"""Tests for context-local configuration state."""

import asyncio
import gc
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, ContextVar, copy_context
from typing import cast

import pytest
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import EnvSettingsSource, InitSettingsSource

from confidantic import ConfigModelDict as ConfigModelDict
from confidantic.context import _CONTEXT_VARS, BaseContext, _context_var


class ExampleContext(BaseContext):
    """Context used across lifecycle tests."""

    value: int = 1


class OtherContext(BaseContext):
    """Independent context used for type and isolation tests."""

    name: str = "other"


@pytest.fixture(autouse=True)
def isolate_contexts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level context variables between tests."""
    monkeypatch.setitem(_CONTEXT_VARS, ExampleContext, ContextVar("EXAMPLE_CONTEXT"))
    monkeypatch.setitem(_CONTEXT_VARS, OtherContext, ContextVar("OTHER_CONTEXT"))


def test_construction_does_not_activate_context() -> None:
    """Ordinary construction remains independent of ambient state."""
    baseline = ExampleContext.current()
    candidate = ExampleContext(value=2)

    assert candidate.value == 2
    assert ExampleContext.current() is baseline


def test_current_lazily_resolves_and_retains_settings_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first lookup resolves settings once and retains provenance."""

    class EnvironmentContext(BaseContext):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: int = 1

    monkeypatch.setenv("APP_VALUE", "2")
    current = EnvironmentContext.current()
    monkeypatch.setenv("APP_VALUE", "3")

    assert current.value == 2
    assert current.model_field_sources == {
        "value": (EnvSettingsSource, EnvironmentContext)
    }
    assert EnvironmentContext.current() is current


def test_set_activates_existing_instance() -> None:
    """Persistent activation retains object identity."""
    context = ExampleContext(value=2)

    assert ExampleContext.set(context) is context
    assert ExampleContext.current() is context


def test_set_rejects_another_context_type() -> None:
    """A context class cannot activate another context type."""
    context = cast(ExampleContext, OtherContext())

    with pytest.raises(TypeError, match="Expected an instance of ExampleContext"):
        ExampleContext.set(context)


def test_context_subclasses_have_independent_storage() -> None:
    """Every subclass receives a distinct context variable."""
    example = ExampleContext(value=2)
    other = OtherContext(name="changed")

    ExampleContext.set(example)
    OtherContext.set(other)

    assert _context_var(ExampleContext) is not _context_var(OtherContext)
    assert ExampleContext.current() is example
    assert OtherContext.current() is other


def test_temporary_context_restores_active_instance() -> None:
    """A temporary activation restores the prior instance on exit."""
    baseline = ExampleContext.set(ExampleContext(value=1))
    temporary = ExampleContext(value=2)

    with ExampleContext.temporary(temporary) as active:
        assert active is temporary
        assert ExampleContext.current() is temporary

    assert ExampleContext.current() is baseline


def test_temporary_rejects_another_context_type() -> None:
    """A context class cannot temporarily activate another context type."""
    context = cast(ExampleContext, OtherContext())

    with (
        pytest.raises(TypeError, match="Expected an instance of ExampleContext"),
        ExampleContext.temporary(context),
    ):
        pass


def test_temporary_context_restores_after_exception() -> None:
    """Temporary activation is exception-safe."""
    baseline = ExampleContext.set(ExampleContext(value=1))

    with (
        pytest.raises(RuntimeError, match="failed"),
        ExampleContext.temporary(ExampleContext(value=2)),
    ):
        raise RuntimeError("failed")

    assert ExampleContext.current() is baseline


def test_temporary_contexts_restore_in_stack_order() -> None:
    """Nested activations restore the outer and baseline instances."""
    baseline = ExampleContext.set(ExampleContext(value=1))
    outer = ExampleContext(value=2)
    inner = ExampleContext(value=3)

    with ExampleContext.temporary(outer):
        with ExampleContext.temporary(inner):
            assert ExampleContext.current() is inner
        assert ExampleContext.current() is outer

    assert ExampleContext.current() is baseline


def test_first_temporary_context_supports_required_fields() -> None:
    """A temporary instance does not require a constructible baseline."""

    class RequiredContext(BaseContext):
        value: int

    context = RequiredContext(value=1)

    with RequiredContext.temporary(context):
        assert RequiredContext.current() is context

    with pytest.raises(ValidationError):
        RequiredContext.current()


def test_activation_does_not_revalidate_or_change_alias_provenance() -> None:
    """Activation retains validated aliases, values, and private provenance."""
    validator_calls = 0

    class AliasedContext(BaseContext):
        value: int = Field(1, alias="VALUE")

        @field_validator("value")
        @classmethod
        def count_validation(cls, value: int) -> int:
            nonlocal validator_calls
            validator_calls += 1
            return value * 2

    context = AliasedContext(VALUE=4)
    calls_after_construction = validator_calls

    AliasedContext.set(context)
    with AliasedContext.temporary(context):
        assert AliasedContext.current() is context

    assert context.value == 8
    assert context.model_field_sources == {
        "value": (InitSettingsSource, AliasedContext)
    }
    assert validator_calls == calls_after_construction


def test_copied_execution_context_isolates_replacement() -> None:
    """Replacing an active instance in a copied context does not leak."""
    parent = ExampleContext.set(ExampleContext(value=1))
    child_context = copy_context()
    child = ExampleContext(value=2)

    child_context.run(ExampleContext.set, child)

    assert child_context.run(ExampleContext.current) is child
    assert ExampleContext.current() is parent


def test_parent_and_same_name_contexts_are_independent() -> None:
    """Registry keys distinguish concrete classes rather than their names."""

    def make_context() -> type[ExampleContext]:
        class Local(ExampleContext):
            pass

        return Local

    first, second = make_context(), make_context()
    ExampleContext.set(ExampleContext(value=9))
    first.set(first(value=2))
    assert second.current().value == 1
    assert first.current().value == 2
    assert ExampleContext.current().value == 9


def test_inactive_context_class_can_be_collected() -> None:
    """Allocating storage does not retain a class after temporary activation."""

    class Local(BaseContext):
        value: int = 1

    reference = weakref.ref(Local)
    with Local.temporary(Local()):
        assert Local.current().value == 1
    del Local
    gc.collect()
    assert reference() is None


def test_temporary_preserves_unrelated_context_changes() -> None:
    """Resetting one class does not roll back another class's activation."""
    with ExampleContext.temporary(ExampleContext(value=9)):
        OtherContext.set(OtherContext(name="changed"))
    assert ExampleContext.current().value == 1
    assert OtherContext.current().name == "changed"


def test_context_thread_isolation() -> None:
    """Threads share one storage variable but retain independent active values."""
    baseline = ExampleContext.set(ExampleContext(value=99))

    def worker(value: int) -> tuple[int, int]:
        def fresh() -> tuple[int, int]:
            assert ExampleContext.current().value == 1
            ExampleContext.set(ExampleContext(value=value))
            return id(_context_var(ExampleContext)), ExampleContext.current().value

        return Context().run(fresh)

    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(worker, range(8)))
    assert len({key for key, _ in result}) == 1
    assert [value for _, value in result] == list(range(8))
    assert ExampleContext.current() is baseline


def test_context_async_task_isolation() -> None:
    """Concurrent temporary activations restore each task's inherited value."""
    baseline = ExampleContext.set(ExampleContext(value=99))

    async def worker(value: int) -> None:
        with ExampleContext.temporary(ExampleContext(value=value)):
            await asyncio.sleep(0)
            assert ExampleContext.current().value == value
        assert ExampleContext.current() is baseline

    async def run() -> None:
        await asyncio.gather(worker(2), worker(3))

    asyncio.run(run())
    assert ExampleContext.current() is baseline
