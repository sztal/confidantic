"""Regressions for the semantic docstring audit."""

from collections.abc import Callable
from typing import Annotated, Any, NewType, Optional

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticSerializationError
from pydantic_settings import CliSettingsSource, InitSettingsSource

from confidantic import BaseConfig, ClassDefaultsSource, Factory
from confidantic.annotations import Make


class AuditTarget:
    """Importable constructor for directive round trips."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


class AuditChild(AuditTarget):
    """Compatible subclass for factory validation."""


class AuditOther:
    """Unrelated factory target."""


_DEFAULT_TARGET = AuditTarget()


class AuditParent:
    """Target containing a concrete default."""

    def __init__(self, child: AuditTarget = _DEFAULT_TARGET) -> None:
        self.child = child


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_factory_target_compatibility(strict: bool, nested: bool) -> None:
    class Config(BaseModel):
        target: Factory[AuditTarget]

    adapter = TypeAdapter(Config if nested else Factory[AuditTarget])
    wrong = Factory.instance_from(AuditOther)
    with pytest.raises(ValidationError, match="expected target"):
        adapter.validate_python({"target": wrong} if nested else wrong, strict=strict)
    for target in (AuditTarget, AuditChild):
        original = Factory.instance_from(target)
        result = adapter.validate_python(
            {"target": original} if nested else original, strict=strict
        )
        assert (result.target if nested else result) is original


@pytest.mark.parametrize(
    "value", [AuditTarget, AuditTarget(), Factory.model_from(AuditTarget)]
)
def test_factory_strict_input_shapes(value: Any) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Factory[AuditTarget]).validate_python(value, strict=True)


@pytest.mark.parametrize(
    "selector",
    [
        AuditTarget,
        AuditTarget | None,
        Optional[AuditTarget],  # noqa: UP045 - callable typing alias regression
        Annotated[AuditTarget, "tag"],
        NewType("TargetAlias", AuditTarget),
    ],
    ids=["class", "union", "optional", "annotated", "newtype"],
)
def test_recursive_annotation_selectors(selector: Any) -> None:
    model = Factory.model_from(AuditParent, __recursive__=selector)
    assert isinstance(model().child, Factory)
    assert model().model_resolve().child.value == 1


def test_recursive_selector_does_not_call_constructor() -> None:
    calls: list[Any] = []

    class Target:
        def __init__(self, value: int = 1) -> None:
            calls.append(value)

    class Parent:
        def __init__(self, value: int = 3) -> None:
            self.value = value

    assert (
        Factory.model_from(Parent, __recursive__=Annotated[Target, "tag"])().value == 3
    )
    assert calls == []


@pytest.mark.parametrize("method", ["copy", "deepcopy", "mutate"])
@pytest.mark.parametrize("updates", [{"other": 2}, {"value": 2}])
def test_copy_source_winners(method: str, updates: dict[str, int]) -> None:
    class Config(BaseConfig, cli_parse_args=["--value", "9"]):
        value: int = 1
        other: int = 0

    original = Config(_cli_parse_args=False)
    result = getattr(original, method)(**updates)
    assert result.value == 9
    assert result.model_field_sources["value"] == (CliSettingsSource, Config)
    assert result.model_fields_set == {"value", *updates}


@pytest.mark.parametrize(
    "source_type", [InitSettingsSource, type("CustomInit", (InitSettingsSource,), {})]
)
def test_copy_custom_initialization_source(source_type: Any) -> None:
    class Config(BaseConfig):
        value: int = 1
        other: int = 0

        @classmethod
        def settings_customise_sources(
            cls, settings_cls: Any, init_settings: Any, **kwargs: Any
        ) -> Any:
            return source_type(settings_cls, {"value": 1}), init_settings

    original = Config.model_construct(value=1, _fields_set=set())
    copied = original.copy(other=2)
    assert copied.model_field_sources["value"] == (source_type, Config)
    assert copied.model_fields_set == {"value", "other"}


def test_copy_preserves_carryover_provenance_after_validation() -> None:
    class Config(BaseConfig):
        value: int = 1
        other: int = 0

        @field_validator("value")
        @classmethod
        def double(cls, value: int) -> int:
            return value * 2

    copied = Config().copy(other=2)
    assert copied.value == 4
    assert copied.model_field_sources["value"] == (ClassDefaultsSource, Config)
    assert copied.model_fields_set == {"other"}


@pytest.mark.parametrize("method", ["copy", "deepcopy", "mutate"])
@pytest.mark.parametrize("extra", ["allow", "ignore"])
def test_copy_extra_metadata(method: str, extra: Any) -> None:
    class Config(BaseConfig, extra=extra):
        value: int = 1

    result = getattr(Config(), method)(label="new")
    assert result.model_fields_set == ({"label"} if extra == "allow" else set())


@pytest.mark.parametrize(
    ("alias", "updates"),
    [
        ("VALUE", {"VALUE": 3}),
        ("VALUE", {"VaLuE": 3}),
        (AliasChoices("VALUE", "other"), {"other": 3}),
        (AliasPath("data", "value"), {"data": {"value": 3}}),
    ],
)
def test_copy_alias_updates(alias: Any, updates: dict[str, Any]) -> None:
    class Config(BaseConfig):
        value: int = Field(1, validation_alias=alias)

    result = Config().copy(**updates)
    assert result.value == 3
    assert result.model_fields_set == {"value"}
    assert result.model_field_sources["value"] == (InitSettingsSource, Config)


class AuditPortable(Factory.model_from(AuditTarget), extra="allow"):
    """Factory with metadata and an aliased constructor field."""

    value: int = Field(1, serialization_alias="VALUE")
    label: str = "metadata"

    @computed_field
    @property
    def computed(self) -> str:
        return "metadata"

    @field_serializer("value")
    def serialize_value(self, value: int) -> int:
        return value + 1


@pytest.mark.parametrize("by_alias", [False, True])
@pytest.mark.parametrize("json_mode", [False, True])
def test_make_constructor_projection(by_alias: bool, json_mode: bool) -> None:
    config = AuditPortable(extra_label="extra")
    if json_mode:
        result = TypeAdapter(Make[Any]).validate_json(
            config.model_dump_json(context={"make": True}, by_alias=by_alias)
        )
    else:
        result = TypeAdapter(Make[Any]).validate_python(
            config.model_dump(context={"make": True}, by_alias=by_alias)
        )
    assert type(result) is AuditTarget
    assert result.value == 2
    assert "label" in config.model_dump()
    assert config.model_dump(context={"make": True}, exclude={"value"}) == {
        "@call": "tests.test_config_regressions:AuditTarget"
    }


def test_make_alias_collision_is_explicit() -> None:
    class Conflicting(AuditPortable):
        other: int = Field(9, serialization_alias="VALUE")

    with pytest.raises(PydanticSerializationError, match="Ambiguous"):
        Conflicting().model_dump(context={"make": True}, by_alias=True)


@pytest.mark.parametrize("dump", ["model_dump", "model_dump_json"])
def test_factory_serializer_error_propagates(dump: str) -> None:
    class Broken(Factory.model_from(AuditTarget)):
        @field_serializer("value")
        def broken(self, value: int) -> int:
            raise ValueError("deliberate serializer failure")

    with pytest.raises(
        PydanticSerializationError, match="deliberate serializer failure"
    ):
        getattr(Broken(), dump)()


def test_recursive_model_annotations_with_finite_values() -> None:
    class Node(BaseModel, arbitrary_types_allowed=True):
        child: "Node | None" = None
        target: Factory[AuditTarget] = Factory.model_from(AuditTarget)

    class Config(BaseConfig):
        first: Node
        second: Node

    original = Config(first=Node(child=Node()), second=Node())
    result = original.model_resolve(name="ResolvedConfig")
    assert type(result).__name__ == "ResolvedConfig"
    assert type(result.first) is type(result.second) is type(result.first.child)
    assert isinstance(result.first.target, AuditTarget)
    assert isinstance(result.first.child.target, AuditTarget)
    assert Node.model_fields["target"].annotation is Factory[AuditTarget]
    assert result.first.target is not result.second.target


def test_unaffected_recursive_annotation_and_actual_cycle() -> None:
    class Node(BaseModel):
        child: "Node | None" = None

    class Config(BaseConfig):
        node: Node
        target: Factory[AuditTarget] = Factory.model_from(AuditTarget)

    assert Config(node=Node(child=Node())).model_resolve().node.child is not None
    node = Node()
    node.child = node
    with pytest.raises(ValueError, match="cyclic values"):
        Config.model_construct(node=node).model_resolve()


def test_mutually_recursive_model_annotations() -> None:
    class Left(BaseModel, arbitrary_types_allowed=True):
        right: "Right | None" = None
        target: Factory[AuditTarget] = Factory.model_from(AuditTarget)

    class Right(BaseModel):
        left: Left | None = None

    Left.model_rebuild()

    class Config(BaseConfig):
        left: Left

    result = Config(left=Left(right=Right(left=Left()))).model_resolve()
    assert isinstance(result.left.right.left.target, AuditTarget)
    assert type(result.left) is type(result.left.right.left)


class AuditOptions(BaseConfig):
    """Settings with a context-sensitive validator."""

    count: int = 1

    @field_validator("count")
    @classmethod
    def offset(cls, value: int, info: ValidationInfo) -> int:
        return value + (info.context or {}).get("offset", 0)


@pytest.mark.parametrize(
    ("loader", "data"),
    [
        ("model_validate", {"count": "2"}),
        ("model_validate_json", '{"count":"2"}'),
        ("model_validate_yaml", 'count: "2"'),
        ("model_validate_toml", 'count = "2"'),
    ],
)
def test_settings_per_call_strictness(loader: str, data: Any) -> None:
    with pytest.raises(ValidationError):
        getattr(AuditOptions, loader)(data, strict=True)


@pytest.mark.parametrize(
    "entry", ["python", "json", "yaml", "toml", "adapter", "nested"]
)
def test_settings_context_and_extra_override(entry: str) -> None:
    options = {"context": {"offset": 10}, "extra": "ignore"}
    if entry == "adapter":
        result = TypeAdapter(AuditOptions).validate_python(
            {"count": 2, "unknown": 3}, **options
        )
    elif entry == "nested":

        class Outer(BaseModel):
            child: AuditOptions

        result = Outer.model_validate(
            {"child": {"count": 2, "unknown": 3}}, **options
        ).child
    else:
        loader, data = {
            "python": ("model_validate", {"count": 2, "unknown": 3}),
            "json": ("model_validate_json", '{"count":2,"unknown":3}'),
            "yaml": ("model_validate_yaml", "count: 2\nunknown: 3"),
            "toml": ("model_validate_toml", "count = 2\nunknown = 3"),
        }[entry]
        result = getattr(AuditOptions, loader)(data, **options)
    assert result.count == 12
    assert result.model_extra is None


def test_settings_user_validators_see_merged_values_once() -> None:
    calls: list[tuple[str, Any]] = []

    class Config(BaseConfig, cli_parse_args=["--count", "7"]):
        count: int = 1

        @model_validator(mode="before")
        @classmethod
        def before(cls, value: Any) -> Any:
            calls.append(("before", value["count"]))
            return value

        @model_validator(mode="wrap")
        @classmethod
        def wrap(cls, value: Any, handler: Callable[[Any], Any]) -> Any:
            calls.append(("wrap", value["count"]))
            return handler(value)

    result = Config.model_validate({"count": 2})
    assert result.count == 7
    assert calls == [("wrap", "7"), ("before", "7")]


@pytest.mark.parametrize("case_sensitive", [False, True])
def test_copy_alias_carryover_and_incomplete_paths(case_sensitive: bool) -> None:
    class Config(BaseConfig, case_sensitive=case_sensitive, extra="allow"):
        value: int = Field(1, validation_alias="VALUE")
        nested: int = Field(2, validation_alias=AliasPath("data", "value"))
        other: int = 0

    copied = Config().copy(other=3, data={"unrelated": 9})
    assert (copied.value, copied.nested) == (1, 2)
    assert copied.model_fields_set == {"other", "data"}
    assert copied.model_field_sources["value"] == (ClassDefaultsSource, Config)


def test_copy_static_custom_source_and_bare_callable() -> None:
    class StaticConfig(BaseConfig):
        value: int = 1
        other: int = 0

        @staticmethod
        def settings_customise_sources(
            settings_cls: Any, init_settings: Any, **kwargs: Any
        ) -> Any:
            return InitSettingsSource(settings_cls, {"value": 8}), init_settings

    result = StaticConfig().copy(value=2)
    assert result.value == 8
    assert result.model_field_sources["value"] == (InitSettingsSource, StaticConfig)

    class BareConfig(BaseConfig):
        value: int = 1

        @classmethod
        def settings_customise_sources(cls, settings_cls: Any, **kwargs: Any) -> Any:
            return (lambda: {"value": 9},)

    assert BareConfig().copy(value=2).model_field_sources == {}


def test_copy_extras_retain_only_explicit_metadata() -> None:
    class Config(BaseConfig, extra="allow"):
        value: int = 1

    original = Config(label="old")
    result = original.copy(other="new")
    assert result.model_fields_set == {"label", "other"}
    assert result.model_extra == {"label": "old", "other": "new"}


def test_factory_selector_predicate_and_parameterized_types() -> None:
    from confidantic._config.factory import _matches_factory_selector

    assert _matches_factory_selector([1, 2], list[int])
    assert not _matches_factory_selector(["1"], list[int])
    calls: list[Any] = []

    def predicate(value: Any) -> bool:
        calls.append(value)
        return True

    assert _matches_factory_selector(1, predicate)
    assert not _matches_factory_selector(None, int)
    assert not _matches_factory_selector(Factory.model_from(AuditTarget), predicate)
    assert not _matches_factory_selector(Factory.instance_from(AuditTarget), predicate)
    assert calls == [1]


def test_make_alias_default_and_nested_factories() -> None:
    class Aliased(AuditPortable, serialize_by_alias=True):
        pass

    assert Aliased().model_dump(context={"make": True}) == {
        "@call": "tests.test_config_regressions:AuditTarget",
        "value": 2,
    }
    model = Factory.model_from(AuditParent, __recursive__=AuditTarget)
    result = TypeAdapter(Make[Any]).validate_python(
        model().model_dump(context={"make": True})
    )
    assert isinstance(result, AuditParent)
    assert isinstance(result.child, AuditTarget)
    assert result.child.value == 1


def test_recursive_resolution_keeps_distinct_same_named_types_and_metadata() -> None:
    from pydantic import ConfigDict, create_model

    from confidantic._config.factory import _resolved_annotation

    first_type = create_model(
        "Node",
        __config__=ConfigDict(arbitrary_types_allowed=True),
        target=(Factory[AuditTarget], Factory.model_from(AuditTarget)),
    )
    second_type = create_model(
        "Node",
        __config__=ConfigDict(arbitrary_types_allowed=True),
        target=(Factory[AuditOther], Factory.model_from(AuditOther)),
    )

    class Config(BaseConfig):
        first: first_type
        second: second_type

    result = Config(first=first_type(), second=second_type()).model_resolve()
    assert type(result.first) is not type(result.second)
    assert isinstance(result.first.target, AuditTarget)
    assert isinstance(result.second.target, AuditOther)
    annotation = Annotated[list[Factory[AuditTarget]], Factory[AuditOther]]
    assert (
        _resolved_annotation(annotation)
        == Annotated[list[AuditTarget], Factory[AuditOther]]
    )


def test_settings_factory_options_and_instance_revalidation() -> None:
    model = Factory.model_from(AuditTarget)
    with pytest.raises(ValidationError):
        model.model_validate({"value": "2"}, strict=True)
    assert model.model_validate({"value": 2, "unknown": 3}, extra="ignore").value == 2
    original = AuditOptions(count=2)
    assert AuditOptions.model_validate(original) is original

    class Revalidated(AuditOptions, revalidate_instances="always"):
        pass

    invalid = Revalidated.model_construct(count="wrong")
    with pytest.raises(ValidationError):
        Revalidated.model_validate(invalid)


def test_settings_custom_constructor_and_context_cleanup() -> None:
    from confidantic._config.base import _NESTED_MODEL_BASELINES

    calls: list[int] = []

    class Custom(BaseConfig):
        value: int = 1

        def __init__(self, value: int = 1, **kwargs: Any) -> None:
            calls.append(value)
            super().__init__(value=value + 1, **kwargs)

    assert Custom(value=2).value == 3
    assert Custom.model_validate({"value": 4}).value == 5
    assert calls == [2, 4]
    with pytest.raises(ValidationError):
        AuditOptions.model_validate({"count": "invalid"}, context={"offset": 10})
    assert _NESTED_MODEL_BASELINES.get() is None
    assert AuditOptions(count=2).count == 2


def test_settings_nested_recursive_schema_keeps_options() -> None:
    class Node(BaseConfig):
        child: "Node | None" = None
        value: int = 1

    with pytest.raises(ValidationError):
        Node.model_validate({"child": {"value": "2"}}, strict=True)
    assert (
        Node.model_validate(
            {"child": {"value": 2, "unknown": 3}}, extra="ignore"
        ).child.value
        == 2
    )


def test_copy_detects_customization_of_the_supplied_init_source() -> None:
    class Config(BaseConfig):
        value: int = 1
        other: int = 0

        @classmethod
        def settings_customise_sources(
            cls, settings_cls: Any, init_settings: Any, **kwargs: Any
        ) -> Any:
            init_settings.init_kwargs["value"] = 9
            return (init_settings,)

    original = Config.model_construct(value=1, _fields_set=set())
    result = original.copy(other=2)
    assert result.value == 9
    assert result.model_field_sources["value"] == (InitSettingsSource, Config)
    assert result.model_fields_set == {"value", "other"}
