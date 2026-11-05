"""BaseConfig copying, mutation, and Make serialization."""

from copy import copy, deepcopy
from typing import Any, ClassVar

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    Field,
    PrivateAttr,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic_core import PydanticSerializationError
from pydantic_settings import (
    CliSettingsSource,
    InitSettingsSource,
)

from confidantic import BaseConfig, ClassDefaultsSource, ConfigModelDict, Factory
from confidantic.annotations import Make
from tests._config.factory_targets import ParentTarget, SimpleTarget
from tests._config.models import (
    PolymorphicChildConfig,
    PolymorphicContainer,
    PolymorphicSiblingConfig,
)


class SerializedChildConfig(BaseConfig):
    """Configuration nested in a serialized parent."""

    value: int = 1


class SerializedParentConfig(BaseConfig):
    """Configuration containing another configuration."""

    child: SerializedChildConfig = SerializedChildConfig()


def test_base_config_can_be_instantiated() -> None:
    """The public base class is also a valid empty settings model."""
    assert BaseConfig().model_dump() == {}


def test_base_config_find_dotenv_delegates_to_dotenv_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BaseConfig exposes the discovered dotenv path unchanged."""
    monkeypatch.setattr(
        "confidantic._config.base.find_dotenv",
        lambda: "/tmp/project/.env",
    )

    assert BaseConfig.find_dotenv() == "/tmp/project/.env"


def test_make_serialization_is_opt_in_and_recursive() -> None:
    """Dump context adds ordered Make directives to nested configurations."""
    config = SerializedParentConfig()

    assert config.model_dump() == {"child": {"value": 1}}
    assert config.model_dump(context={"make": True}) == {
        "@call": "tests._config.test_base:SerializedParentConfig",
        "child": {
            "@call": "tests._config.test_base:SerializedChildConfig",
            "value": 1,
        },
    }
    assert config.model_dump_json(context={"make": True}) == (
        '{"@call":"tests._config.test_base:SerializedParentConfig",'
        '"child":{"@call":"tests._config.test_base:SerializedChildConfig",'
        '"value":1}}'
    )


def test_make_serialization_does_not_use_factory_target_attribute() -> None:
    """Only Factory instances use their target for Make directives."""

    class MisleadingConfig(BaseConfig):
        factory_target: ClassVar[type] = str

    assert MisleadingConfig().model_dump(context={"make": True})["@call"] == (
        "tests._config.test_base:test_make_serialization_does_not_use_factory_target_attribute.<locals>.MisleadingConfig"
    )


def test_make_serialization_preserves_dump_options() -> None:
    """Make directives remain independent from aliases and exclusions."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

    assert Config(VALUE=1).model_dump(
        by_alias=True,
        exclude={"value"},
        context={"make": True},
    ) == {
        "@call": "tests._config.test_base:test_make_serialization_preserves_dump_options.<locals>.Config"
    }


def test_make_deserializes_concrete_subclasses() -> None:
    """Make mappings and JSON resolve to their concrete configuration types."""
    config = PolymorphicChildConfig(name="child", count=2)
    data = config.model_dump(context={"make": True})

    resolved = PolymorphicContainer.model_validate({"item": data, "items": []}).item
    resolved_json = PolymorphicContainer.model_validate_json(
        '{"item":' + config.model_dump_json(context={"make": True}) + ',"items":[]}'
    ).item

    assert type(resolved) is PolymorphicChildConfig
    assert resolved == config
    assert type(resolved_json) is PolymorphicChildConfig
    assert resolved_json == config


def test_make_deserializes_nested_subclasses() -> None:
    """Fields and containers retain concrete types selected by Make directives."""
    child = PolymorphicChildConfig(name="child", count=2)
    sibling = PolymorphicSiblingConfig(name="sibling", enabled=False)

    resolved = PolymorphicContainer.model_validate(
        {
            "item": child.model_dump(context={"make": True}),
            "items": [
                child.model_dump(context={"make": True}),
                sibling.model_dump(context={"make": True}),
            ],
        }
    )

    assert type(resolved.item) is PolymorphicChildConfig
    assert type(resolved.items[0]) is PolymorphicChildConfig
    assert type(resolved.items[1]) is PolymorphicSiblingConfig


def test_base_config_is_frozen_by_default() -> None:
    """Configuration fields cannot be reassigned by default."""

    class Config(BaseConfig):
        value: str = "initial"

    config = Config()

    assert Config.model_config["frozen"] is True  # type: ignore[truthy-function]
    with pytest.raises(ValidationError) as error:
        config.value = "changed"

    assert error.value.errors()[0]["type"] == "frozen_instance"


def test_frozen_config_retains_field_sources() -> None:
    """Frozen construction retains default and explicit field provenance."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(frozen=True)

        value: str = "default"

    assert Config().model_field_sources == {
        "value": (ClassDefaultsSource, Config),
    }
    assert Config(value="explicit").model_field_sources == {
        "value": (InitSettingsSource, Config),
    }


def test_frozen_default_is_inherited_with_other_model_options() -> None:
    """Subclass model options preserve the inherited frozen default."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: str = "initial"

    assert Config.model_config["frozen"] is True  # type: ignore[truthy-function]
    with pytest.raises(ValidationError):
        Config().value = "changed"


def test_frozen_default_can_be_disabled() -> None:
    """Subclasses can opt into mutable configuration fields."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(frozen=False)

        value: str = "initial"

    config = Config()
    config.value = "changed"

    assert config.value == "changed"


def test_copy_protocol_preserves_configuration_state() -> None:
    """Copy protocols retain model state with their standard depth semantics."""

    class Config(BaseConfig):
        value: int = 1
        items: list[int]

        _state: dict[str, list[int]] = PrivateAttr(
            default_factory=lambda: {"items": [1]}
        )

    config = Config(items=[1])

    shallow = copy(config)
    deep = deepcopy(config)
    convenience_shallow = config.copy()
    convenience_deep = config.deepcopy()

    assert isinstance(shallow, Config)
    assert shallow is not config
    assert shallow.items is config.items
    assert shallow._state is config._state
    assert shallow.model_fields_set == config.model_fields_set
    assert shallow.model_field_sources == config.model_field_sources
    assert deep.items == config.items
    assert deep.items is not config.items
    assert deep._state == config._state
    assert deep._state is not config._state
    assert convenience_shallow.items is config.items
    assert convenience_deep.items is not config.items
    with pytest.raises(ValidationError):
        shallow.value = 2


def test_copy_methods_validate_updates_and_retain_provenance() -> None:
    """Convenience copies validate updates without replacing inherited sources."""

    class Config(BaseConfig):
        value: int = 1
        defaulted: str = "default"
        items: list[int]

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    config = Config(value=2, items=[1])

    shallow = config.copy(value="3")
    deep = config.deepcopy(value="4")

    assert shallow.value == 6
    assert deep.value == 8
    assert shallow.model_field_sources == {
        "value": (InitSettingsSource, Config),
        "defaulted": (ClassDefaultsSource, Config),
        "items": (InitSettingsSource, Config),
    }
    assert shallow.model_fields_set == {"value", "items"}
    assert shallow._model_field_sources is not config._model_field_sources
    with pytest.raises(ValidationError):
        config.copy(value="invalid")


def test_mutate_validates_frozen_configuration_in_place() -> None:
    """Frozen configurations can be validated and updated in place explicitly."""

    class Config(BaseConfig):
        value: int = 1
        defaulted: str = "default"

        _state: list[str] = PrivateAttr(default_factory=list)

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    config = Config()
    state = config._state
    original_hash = hash(config)

    assert config.mutate(value="3") is config
    assert config.value == 6
    assert hash(config) != original_hash
    assert config.model_field_sources == {
        "value": (InitSettingsSource, Config),
        "defaulted": (ClassDefaultsSource, Config),
    }
    assert config.model_fields_set == {"value"}
    assert config._state is state
    with pytest.raises(ValidationError):
        config.value = 2

    with pytest.raises(ValidationError):
        config.mutate(value="invalid")

    assert config.value == 6
    assert config.model_fields_set == {"value"}


def test_missing_required_field_raises_validation_error() -> None:
    """Required fields remain errors after all MRO levels are exhausted."""

    class Config(BaseConfig):
        value: str

    with pytest.raises(ValidationError):
        Config()


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


class PortableFactory(Factory.model_from(SimpleTarget), extra="allow"):
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
    config = PortableFactory(extra_label="extra")
    if json_mode:
        result = TypeAdapter(Make[Any]).validate_json(
            config.model_dump_json(context={"make": True}, by_alias=by_alias)
        )
    else:
        result = TypeAdapter(Make[Any]).validate_python(
            config.model_dump(context={"make": True}, by_alias=by_alias)
        )
    assert type(result) is SimpleTarget
    assert result.value == 2
    assert "label" in config.model_dump()
    assert config.model_dump(context={"make": True}, exclude={"value"}) == {
        "@call": "tests._config.factory_targets:SimpleTarget"
    }


def test_make_alias_collision_is_explicit() -> None:
    class Conflicting(PortableFactory):
        other: int = Field(9, serialization_alias="VALUE")

    with pytest.raises(PydanticSerializationError, match="Ambiguous"):
        Conflicting().model_dump(context={"make": True}, by_alias=True)


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


def test_make_alias_default_and_nested_factories() -> None:
    class Aliased(PortableFactory, serialize_by_alias=True):
        pass

    assert Aliased().model_dump(context={"make": True}) == {
        "@call": "tests._config.factory_targets:SimpleTarget",
        "value": 2,
    }
    model = Factory.model_from(ParentTarget, __recursive__=SimpleTarget)
    result = TypeAdapter(Make[Any]).validate_python(
        model().model_dump(context={"make": True})
    )
    assert isinstance(result, ParentTarget)
    assert isinstance(result.child, SimpleTarget)
    assert result.child.value == 1


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
