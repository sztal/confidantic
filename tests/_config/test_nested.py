"""Partial updates to nested models and their concrete defaults."""

from typing import Any, Literal

import pytest
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_settings import (
    EnvSettingsSource,
    InitSettingsSource,
)

from confidantic import BaseConfig, ConfigModelDict


def test_partial_cli_update_preserves_nested_factory_model() -> None:
    """A CLI patch retains the factory model's concrete type and defaults."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2
        child_only: int = 3

    class Config(BaseConfig):
        nested: Nested = Field(default_factory=NestedChild)

    config = Config(_cli_parse_args=["--nested.x=11"])

    assert type(config.nested) is NestedChild
    assert config.nested == NestedChild(x=11)


def test_nested_factory_model_is_partially_updated_from_env_and_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mapping sources patch the factory model and retain their provenance."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        nested: Nested = Field(default_factory=NestedChild)

    monkeypatch.setenv("APP_NESTED__X", "11")
    environment = Config()
    monkeypatch.delenv("APP_NESTED__X")
    explicit_mapping = Config(nested={"x": "12"})

    assert type(environment.nested) is NestedChild
    assert environment.nested == NestedChild(x=11)
    assert environment.model_field_sources["nested"] == (EnvSettingsSource, Config)
    assert type(explicit_mapping.nested) is NestedChild
    assert explicit_mapping.nested == NestedChild(x=12)
    assert explicit_mapping.model_field_sources["nested"] == (
        InitSettingsSource,
        Config,
    )


def test_partial_update_uses_static_or_explicit_nested_model_baseline() -> None:
    """A patch retains the concrete type and current values of its baseline."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2
        child_only: int = 3

    class Config(BaseConfig):
        nested: Nested = NestedChild(y=7)

    static = Config(_cli_parse_args=["--nested.x=11"])
    base = Nested(x=2, y=8)
    explicit = Config(nested=base)
    patched_explicit = Config(
        nested=base,
        _cli_parse_args=["--nested.x=12"],
    )

    assert type(static.nested) is NestedChild
    assert static.nested == NestedChild(x=11, y=7)
    assert explicit.nested is base
    assert type(patched_explicit.nested) is Nested
    assert patched_explicit.nested == Nested(x=12, y=8)


def test_partial_update_evaluates_validated_data_model_factory_once() -> None:
    """A partial update defers one data-aware factory call to validation."""
    calls = 0

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    def make_nested(data: dict[str, Any]) -> NestedChild:
        nonlocal calls
        calls += 1
        return NestedChild(y=data["seed"])

    class Config(BaseConfig):
        seed: int = 3
        nested: Nested = Field(default_factory=make_nested)

    config = Config(
        seed="7",
        _cli_parse_args=["--nested.x=11"],
    )

    assert type(config.nested) is NestedChild
    assert config.nested == NestedChild(x=11, y=7)
    assert calls == 1


def test_mapping_source_does_not_evaluate_non_model_factory() -> None:
    """A supplied mapping does not evaluate an unrelated mapping factory."""
    calls = 0

    def make_values() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"default": 1}

    class Config(BaseConfig):
        values: dict[str, int] = Field(default_factory=make_values)

    config = Config(values={"provided": 2})

    assert config.values == {"provided": 2}
    assert calls == 0


def test_partial_update_recurses_through_plain_pydantic_models() -> None:
    """Direct BaseModel fields retain runtime types at every nested level."""

    class Inner(BaseModel):
        x: int = Field(1, alias="X")
        y: int = 1

        @field_validator("x")
        @classmethod
        def double_x(cls, value: int) -> int:
            return value * 2

    class InnerChild(Inner):
        y: int = 2
        child_only: int = 3

    class Outer(BaseModel):
        inner: Inner = InnerChild(X=1)

    class OuterChild(Outer):
        outer_only: int = 4

    class Config(BaseConfig):
        nested: Outer = Field(default_factory=OuterChild)

    config = Config(nested={"inner": {"X": "5"}})

    assert type(config.nested) is OuterChild
    assert type(config.nested.inner) is InnerChild
    assert config.nested.inner == InnerChild(X=5)
    assert config.nested.model_fields_set == {"inner"}
    assert config.nested.inner.model_fields_set == {"x"}


def test_nested_model_partial_update_can_be_disabled() -> None:
    """Class and instance opt-outs retain the original Pydantic behavior."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    class Config(BaseConfig):
        model_config = ConfigModelDict(
            nested_model_default_partial_update=False,
        )

        nested: Nested = Field(default_factory=NestedChild)

    class InstanceOverrideConfig(BaseConfig):
        nested: Nested = Field(default_factory=NestedChild)

    configured = Config(_cli_parse_args=["--nested.x=11"])
    overridden = InstanceOverrideConfig(
        _nested_model_default_partial_update=False,
        _cli_parse_args=["--nested.x=12"],
    )

    assert type(configured.nested) is Nested
    assert configured.nested == Nested(x=11)
    assert type(overridden.nested) is Nested
    assert overridden.nested == Nested(x=12)


def test_discriminated_nested_model_update_selects_replacement_variant() -> None:
    """A discriminator selects a variant without values from the default."""

    class First(BaseModel):
        kind: Literal["first"] = "first"
        shared: int = 7

    class Second(BaseModel):
        kind: Literal["second"] = "second"
        shared: int = 2

    class Config(BaseConfig):
        nested: First | Second = Field(
            default=First(),
            discriminator="kind",
        )

    config = Config(nested={"kind": "second"})

    assert type(config.nested) is Second
    assert config.nested == Second()


@pytest.mark.parametrize("inner_fails", [False, True])
def test_reentrant_validation_restores_outer_baselines(inner_fails: bool) -> None:
    """Nested validation restores the outer model's partial-update baselines."""

    class Nested(BaseModel):
        value: int = 1
        retained: int = 2

    class Inner(BaseConfig):
        nested: Nested = Nested(retained=99)

    class Outer(BaseConfig):
        trigger: int = 0
        nested: Nested = Nested(retained=20)

        @field_validator("trigger")
        @classmethod
        def validate_inner(cls, value: int) -> int:
            if inner_fails:
                with pytest.raises(ValidationError):
                    Inner(nested={"value": "invalid"})
            else:
                assert Inner(nested={"value": 7}).nested.retained == 99
            return value

    result = Outer(nested={"value": 4})
    assert result.nested == Nested(value=4, retained=20)
    assert Inner(nested={"value": 9}).nested == Nested(value=9, retained=99)


@pytest.mark.parametrize("default_factory", [False, True], ids=["static", "factory"])
@pytest.mark.parametrize(
    "partial_update",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="BUGS.md: nested model partial updates lose per-call validation options",
            ),
        ),
    ],
    ids=["replacement", "partial-update"],
)
@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("strict", ("int_type",)),
        ("context", 12),
        ("extra_forbid", ("extra_forbidden",)),
        ("extra_ignore", 2),
    ],
)
def test_nested_updates_forward_validation_options(
    default_factory: bool,
    partial_update: bool,
    case: str,
    expected: int | tuple[str, ...],
) -> None:
    """Nested reconstruction should retain outer strictness, context, and extra policy."""

    class Nested(BaseModel, extra="forbid" if case == "extra_ignore" else "ignore"):
        count: int = 1

        @field_validator("count")
        @classmethod
        def offset(cls, value: int, info: ValidationInfo) -> int:
            return value + (info.context or {}).get("offset", 0)

    class Config(BaseConfig, nested_model_default_partial_update=partial_update):
        nested: Nested = Field(default_factory=Nested) if default_factory else Nested()

    data, options = {
        "strict": ({"count": "2"}, {"strict": True}),
        "context": ({"count": 2}, {"context": {"offset": 10}}),
        "extra_forbid": ({"count": 2, "unknown": 3}, {"extra": "forbid"}),
        "extra_ignore": ({"count": 2, "unknown": 3}, {"extra": "ignore"}),
    }[case]
    actual: int | tuple[str, ...]
    try:
        result = Config.model_validate({"nested": data}, **options)
    except ValidationError as error:
        actual = tuple(item["type"] for item in error.errors())
    else:
        actual = result.nested.count
    assert actual == expected


@pytest.mark.parametrize("has_default", [False, True])
def test_optional_model_factory_can_supply_or_omit_a_baseline(
    has_default: bool,
) -> None:
    """Optional defaults merge when present and validate supplied mappings when absent."""

    class Nested(BaseModel):
        value: int = 1
        retained: int = 2

    class Config(BaseConfig):
        nested: Nested | None = Field(
            default_factory=lambda: Nested(retained=9) if has_default else None
        )

    assert Config(nested={"value": 7}).nested == Nested(
        value=7, retained=9 if has_default else 2
    )
