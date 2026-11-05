"""Tests for configurable classes and their instance configurations."""

from copy import copy, deepcopy
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from confidantic.configurable import Configurable, InstanceConfig


class WidgetConfig(InstanceConfig):
    """Configuration used by :class:`Widget`."""

    name: str = "default"
    options: dict[str, int] = Field(default_factory=lambda: {"retries": 3})


class Widget(Configurable):
    """Configurable object used by the tests."""

    Config = WidgetConfig


class HashableWidgetConfig(InstanceConfig):
    """Hashable configuration used to test identity operations."""

    name: str = "default"


class HashableWidget(Configurable):
    """Configurable object with a hashable configuration."""

    Config = HashableWidgetConfig


class ConfigInput(BaseModel):
    """Pydantic input model for configuration conversion tests."""

    name: str


def test_nested_config_tracks_its_parent_and_constructs_it() -> None:
    """Nested configs receive their owner and can materialize it."""
    config = WidgetConfig(name="configured")

    widget = config.to_parent()

    assert WidgetConfig.Parent is Widget
    assert isinstance(widget, Widget)
    assert widget.config is config


def test_subclasses_only_associate_directly_declared_configs() -> None:
    """Inherited configuration classes retain their original parent association."""

    class IncompleteConfig(WidgetConfig):
        pass

    class InheritedConfigWidget(Widget):
        pass

    with pytest.raises(TypeError, match="without a valid 'Parent' class attribute"):
        IncompleteConfig().to_parent()

    assert WidgetConfig.Parent is Widget
    assert InheritedConfigWidget().config.name == "default"

    class ConcreteConfigWidget(Widget):
        Config = IncompleteConfig

    assert IncompleteConfig.Parent is ConcreteConfigWidget
    assert isinstance(IncompleteConfig().to_parent(), ConcreteConfigWidget)


@pytest.mark.parametrize(
    ("config", "kwargs", "expected_name"),
    [
        (None, {"name": "keywords"}, "keywords"),
        ({"name": "mapping"}, {}, "mapping"),
        (ConfigInput(name="model"), {}, "model"),
    ],
)
def test_configurable_accepts_config_input_forms(
    config: WidgetConfig | ConfigInput | dict[str, str] | None,
    kwargs: dict[str, str],
    expected_name: str,
) -> None:
    """Construction accepts defaults, mappings, and Pydantic models."""
    widget = Widget(config, **kwargs)

    assert isinstance(widget.config, WidgetConfig)
    assert widget.config.name == expected_name


def test_configurable_rejects_invalid_config_input() -> None:
    """Construction rejects values that are not configuration inputs."""
    with pytest.raises(TypeError, match="Expected config of type WidgetConfig"):
        Widget(1)  # type: ignore[arg-type]


def test_configurable_replaces_existing_config_when_given_updates() -> None:
    """Keyword updates derive a validated configuration without mutating the input."""
    config = WidgetConfig(name="original")

    widget = Widget(config, name="replacement")

    assert widget.config is not config
    assert config.name == "original"
    assert widget.config.name == "replacement"


def test_configurable_copying_and_reconfiguration_follow_config_semantics() -> None:
    """Copies retain shallow/deep configuration behavior and accept updates."""
    widget = Widget({"name": "original", "options": {"retries": 2}})

    shallow = copy(widget)
    deep = deepcopy(widget)
    updated = widget.copy(name="copy")
    deep_updated = widget.deepcopy(name="deep copy")

    assert shallow is not widget
    assert shallow.config.options is widget.config.options
    assert deep.config.options is not widget.config.options
    assert updated.config.name == "copy"
    assert deep_updated.config.name == "deep copy"
    assert deep_updated.config.options is not widget.config.options

    widget.reconfigure(name="updated")

    assert widget.config.name == "updated"
    assert widget.rc(name="aliased") is widget
    assert widget.config.name == "aliased"


def test_configurable_equality_and_hash_follow_the_configuration() -> None:
    """Equal objects with hashable configurations compare and hash equally."""
    first = HashableWidget(name="same")
    equal = HashableWidget(name="same")
    different = HashableWidget(name="different")

    assert first == equal
    assert first != different
    assert hash(first) == hash(equal)
    assert first.__eq__(object()) is NotImplemented


def test_configurable_state_round_trips_through_pickle() -> None:
    """State dunder methods preserve configuration during pickling."""
    widget = Widget(name="pickled")
    state = widget.__getstate__()
    restored = Widget.__new__(Widget)

    restored.__setstate__(state)

    assert state == {"config": widget.config}
    assert restored.config is widget.config
    assert restored == widget


def test_configurable_state_validates_the_concrete_configuration() -> None:
    """State mappings are validated before they are installed on the object."""
    restored = Widget.__new__(Widget)

    restored.__setstate__({"config": {"name": "restored", "options": {}}})

    assert isinstance(restored.config, WidgetConfig)
    assert restored.config.name == "restored"
    with pytest.raises(ValidationError):
        restored.__setstate__({"config": {"options": {"retries": "invalid"}}})


def test_configurable_info_forwards_arguments_to_its_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The information helper delegates arguments and its return value unchanged."""
    widget = Widget()
    result = object()

    def info(config: WidgetConfig, *args: Any, **kwargs: Any) -> object:
        assert config is widget.config
        assert args == ("name",)
        assert kwargs == {"show_sources": True}
        return result

    monkeypatch.setattr(WidgetConfig, "info", info)

    assert widget.info("name", show_sources=True) is result


@pytest.mark.parametrize(
    "config_class",
    [None, "invalid", BaseModel],
)
def test_configurable_rejects_missing_or_invalid_config_class(
    config_class: object,
) -> None:
    """Invalid declarations raise the module's concise configuration error."""

    class InvalidConfigurable(Configurable):
        Config = config_class

    with pytest.raises(TypeError, match="without a valid 'Config' class attribute"):
        InvalidConfigurable()


def test_configurable_converts_unrelated_configuration_instances() -> None:
    """Other configuration models provide their dumped values as constructor input."""

    class OtherConfig(InstanceConfig):
        name: str = "other"

    widget = Widget(OtherConfig())

    assert isinstance(widget.config, WidgetConfig)
    assert widget.config.name == "other"


@pytest.mark.parametrize("mode", ["excluded", "serializer"])
def test_equality_uses_stored_values(mode: str) -> None:
    """Serialization must not erase distinctions used by configuration hashing."""
    from pydantic import field_serializer

    class Options(InstanceConfig):
        value: int = Field(exclude=mode == "excluded")

        @field_serializer("value")
        def serialize_value(self, value: int) -> int:
            return 0

    class Component(Configurable):
        Config = Options

    first, different, equal = Component(value=1), Component(value=2), Component(value=1)
    assert first.config.model_dump() == different.config.model_dump()
    assert first != different
    assert first == equal and hash(first) == hash(equal)
    assert equal in {first}
    assert {first: "found"}[equal] == "found"
    assert different not in {first}


def test_equality_ignores_provenance_but_checks_types_and_extras() -> None:
    """Only stored public configuration state determines runtime equality."""
    from pydantic import computed_field

    class Options(InstanceConfig, extra="allow"):
        value: int = 1

        @computed_field
        @property
        def source(self) -> str:
            return self.model_field_sources["value"][0].__name__

    class DerivedOptions(Options):
        pass

    class Component(Configurable):
        Config = Options

    class Child(Component):
        pass

    first, equal = Component(), Component(value=1)
    assert first.config.source != equal.config.source
    assert first == equal and hash(first) == hash(equal)
    assert first == Child() and Child() == first
    assert first != Component(DerivedOptions())
    assert Component(label="a") != Component(label="b")
    assert Component(label="a") == Component(label="a")
    assert first.__eq__(object()) is NotImplemented
    with pytest.raises(TypeError):
        hash(Widget())
