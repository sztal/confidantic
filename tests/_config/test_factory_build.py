"""Constructor inspection, recursive field generation, and copied defaults."""

import sys
from types import ModuleType
from typing import Annotated, Any, ForwardRef, NewType, Optional, Union

import pytest
from pydantic import Field
from pydantic.errors import PydanticUserError
from pydantic_settings import InitSettingsSource
from typing_extensions import TypedDict

from confidantic import ClassDefaultsSource, Factory
from confidantic._config._factory_build import _FactoryModelBuilder
from tests._config.factory_targets import (
    _DEFAULT_SERVICE,
    AlternativeServiceHolder,
    Basket,
    OptionalServiceHolder,
    ParameterizedAlternativeServiceHolder,
    ParentTarget,
    Product,
    RequiredServiceHolder,
    Service,
    ServiceBase,
    ServiceHolder,
    SimpleTarget,
)


def test_model_from_type_creates_typed_config_fields() -> None:
    """Constructor annotations define fields on the generated generic factory."""
    config_type = Factory.model_from(Product)

    assert config_type.__name__ == "ProductConfig"
    assert config_type.__module__ != Product.__module__
    assert not hasattr(sys.modules[config_type.__module__], config_type.__name__)
    assert issubclass(config_type, Factory)
    assert config_type.factory_target is Product
    assert config_type.factory_fields == ("count", "label", "enabled")
    assert tuple(config_type.model_fields) == ("count", "label", "enabled")
    assert config_type.model_fields["count"].is_required()
    assert config_type.model_fields["label"].default == "default"
    assert config_type.model_fields["enabled"].default is True
    assert config_type(count=1).model_dump(context={"make": True})["@call"] == (
        "tests._config.factory_targets:Product"
    )


def test_model_from_type_uses_constructor_arguments_as_defaults() -> None:
    """Type sources can provide positional and keyword constructor defaults."""
    config_type = Factory.model_from(Product, 3, "configured", enabled=False)

    assert config_type().model_dump() == {
        "count": 3,
        "label": "configured",
        "enabled": False,
    }


def test_model_from_rejects_constructor_arguments_for_instance_sources() -> None:
    """Constructor arguments are accepted only when the source is a type."""
    with pytest.raises(
        TypeError, match="constructor arguments require a target type as source"
    ):
        Factory.model_from(Product(3), label="configured")


def test_model_from_recursive_wraps_matching_defaults() -> None:
    """Matching defaults become recursively resolvable factory fields."""
    config_type = Factory.model_from(ServiceHolder, __recursive__=ServiceBase)

    service = config_type().service

    assert service.factory_target is Service
    assert config_type().model_resolve().service.value == 1


def test_model_from_as_factory_accepts_type_hints_and_predicates() -> None:
    """Type hints and callable selectors use the concrete default value."""
    type_hint_config = Factory.model_from(
        ServiceHolder, __recursive__=ServiceBase | None
    )
    predicate_config = Factory.model_from(
        ServiceHolder, __recursive__=lambda value: isinstance(value, Service)
    )

    assert type_hint_config().service.factory_target is Service
    assert predicate_config().service.factory_target is Service
    assert predicate_config.model_fields["label"].annotation is str


def test_model_from_as_factory_predicate_leaves_nonmatching_defaults() -> None:
    """A predicate selector leaves nonmatching concrete defaults unchanged."""
    config_type = Factory.model_from(
        ServiceHolder, __recursive__=lambda value: isinstance(value, str)
    )

    assert config_type().service is _DEFAULT_SERVICE


def test_model_from_as_factory_handles_none_union_defaults() -> None:
    """Type-hint selectors support optional defaults that do not match."""
    config_type = Factory.model_from(
        OptionalServiceHolder, __recursive__=ServiceBase | None
    )

    assert config_type().service is None


def test_model_from_as_factory_uses_instance_values() -> None:
    """Instance sources provide the nested factory's concrete defaults."""
    source = ServiceHolder(Service(7), "configured")

    config_type = Factory.model_from(source, __recursive__=ServiceBase)

    assert config_type().model_resolve().service.value == 7
    assert config_type().model_resolve().label == "configured"


def test_model_from_as_factory_preserves_optional_union_alternatives() -> None:
    """Recursive factories retain explicit None as a valid alternative."""
    config_type = Factory.model_from(
        OptionalServiceHolder(Service(7)), __recursive__=ServiceBase
    )

    assert config_type().service.factory_target is Service
    assert config_type(service=None).service is None
    assert config_type(service=None).model_resolve().service is None


def test_model_from_as_factory_preserves_union_alternatives() -> None:
    """Recursive factories retain unrelated union alternatives."""
    config_type = Factory.model_from(
        AlternativeServiceHolder(Service(7)), __recursive__=ServiceBase
    )

    assert config_type(service=None).service is None
    assert config_type(service="fallback").model_resolve().service == "fallback"


def test_model_from_as_factory_preserves_parameterized_union_alternatives() -> None:
    """Recursive factories leave literal values and metadata unchanged."""
    config_type = Factory.model_from(
        ParameterizedAlternativeServiceHolder(Service(7)),
        __recursive__=ServiceBase,
    )

    assert config_type(service="fallback").model_resolve().service == "fallback"
    assert config_type(service="annotated").model_resolve().service == "annotated"
    assert config_type(service=None).model_resolve().service is None


def test_model_from_as_factory_wraps_required_instance_values() -> None:
    """Instance values can provide defaults for required constructor fields."""
    config_type = Factory.model_from(
        RequiredServiceHolder(Service(7)), __recursive__=ServiceBase
    )

    assert config_type().model_resolve().service.value == 7


def test_model_from_as_factory_leaves_required_fields_unchanged() -> None:
    """Required fields without source values are not auto-generated."""
    config_type = Factory.model_from(RequiredServiceHolder, __recursive__=ServiceBase)

    assert config_type.model_fields["service"].is_required()


def test_model_from_as_factory_preserves_existing_factory_defaults() -> None:
    """Existing factory defaults are not wrapped a second time."""
    factory_type = Factory.model_from(Service)

    class Target:
        def __init__(self, service: Factory[ServiceBase] = factory_type) -> None:
            self.service = service

    config_type = Factory.model_from(Target, __recursive__=ServiceBase)

    assert config_type.model_fields["service"].default is factory_type


def test_model_from_as_factory_isolates_nested_mutable_defaults() -> None:
    """Generated nested factories receive independent mutable defaults."""

    default_values = [1]

    class MutableService:
        def __init__(self, values: list[int] = default_values) -> None:
            self.values = values

    default_service = MutableService()

    class MutableServiceHolder:
        def __init__(self, service: MutableService = default_service) -> None:
            self.service = service

    config_type = Factory.model_from(MutableServiceHolder, __recursive__=MutableService)
    first = config_type()
    second = config_type()

    first.service.values.append(2)

    assert first.service.values == [1, 2]
    assert second.service.values == [1]


def test_factory_selector_supports_type_adapter_fallback() -> None:
    """Type-hint selectors retry when adapter config is not applicable."""

    class Payload(TypedDict):
        value: int

    assert _FactoryModelBuilder.matches_type_hint({"value": 1}, Payload)
    assert not _FactoryModelBuilder.matches_type_hint({"value": "invalid"}, Payload)


def test_factory_selector_propagates_invalid_type_hints() -> None:
    """Invalid selector hints are reported instead of treated as nonmatches."""

    class InvalidSchema:
        @classmethod
        def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
            raise PydanticUserError("invalid schema", code="invalid-schema")

    with pytest.raises(PydanticUserError):
        _FactoryModelBuilder.matches_type_hint(1, InvalidSchema)


def test_model_from_type_accepts_custom_name() -> None:
    """Callers can choose the generated model name."""
    assert (
        Factory.model_from(Product, __name__="ConfiguredProduct").__name__
        == "ConfiguredProduct"
    )


def test_model_from_resolves_annotations_from_base_class_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inherited runtime types are available to nested forward references."""
    base_module = ModuleType("factory_base_module")
    exec(
        "class BaseOptimization(int):\n    pass\n",
        vars(base_module),
    )
    target_namespace = {"__name__": __name__}
    target_namespace["Fallback"] = ForwardRef("BaseOptimization") | None
    exec(
        "def target_init(self, fallback: 'Fallback' = None):\n"
        "    self.fallback = fallback\n",
        target_namespace,
    )
    target = type(
        "Target",
        (base_module.BaseOptimization,),
        {"__module__": __name__, "__init__": target_namespace["target_init"]},
    )
    monkeypatch.setitem(sys.modules, base_module.__name__, base_module)

    config_type = Factory.model_from(target)

    assert config_type().fallback is None


def test_model_from_rejects_annotated_positional_only_parameter() -> None:
    """A config cannot safely represent positional-only target arguments."""

    class PositionalTarget:
        def __init__(self, value: int, /) -> None:
            self.value = value

    with pytest.raises(
        TypeError,
        match=r"PositionalTarget.__init__ parameter 'value' is positional-only",
    ):
        Factory.model_from(PositionalTarget)


def test_model_from_instance_uses_isolated_attribute_defaults() -> None:
    """Mutable instance attributes are copied for every config instance."""
    config_type = Factory.model_from(Basket(["first"], {"count": 1}))
    first = config_type()
    second = config_type()
    first.items.append("second")
    first.metadata["count"] = 2

    assert first.items == ["first", "second"]
    assert first.metadata == {"count": 2}
    assert second.items == ["first"]
    assert second.metadata == {"count": 1}


def test_model_from_instance_copies_custom_unhashable_defaults() -> None:
    """Custom unhashable instance attributes receive isolated defaults."""

    class Unhashable:
        __hash__ = None  # type: ignore[assignment]

    default_value = Unhashable()

    class Target:
        def __init__(self, value: Any = default_value) -> None:
            self.value = value

    config_type = Factory.model_from(Target(Unhashable()))
    first = config_type()
    second = config_type()

    assert first.value is not second.value


def test_model_from_instance_preserves_defaults_for_missing_attributes() -> None:
    """Missing instance attributes do not replace declared constructor defaults."""

    class Target:
        def __init__(self, value: int = 3) -> None:
            pass

    config_type = Factory.model_from(Target())

    assert config_type().value == 3


class HashableList(list[Any]):
    """Mutable list that Pydantic's hash-based default copying would share."""

    __hash__ = object.__hash__  # type: ignore[assignment]


class HashableDict(dict[str, Any]):
    """Mutable mapping with an identity hash."""

    __hash__ = object.__hash__  # type: ignore[assignment]


class HashableSet(set[int]):
    """Mutable set with an identity hash."""

    __hash__ = object.__hash__  # type: ignore[assignment]


@pytest.mark.parametrize(
    "value",
    [
        HashableList([1]),
        HashableDict(a=[1]),
        HashableSet({1}),
        [1],
        {"a": [1]},
        {1},
        bytearray(b"a"),
    ],
)
@pytest.mark.parametrize("from_instance", [False, True])
def test_generated_defaults_are_independent(value: Any, from_instance: bool) -> None:
    """Constructor and instance defaults are isolated regardless of hashability."""

    class Target:
        def __init__(self, items: Any = value) -> None:
            self.items = items

    model = Factory.model_from(Target() if from_instance else Target)
    first, second = model(), model()
    assert first.items == second.items == value
    assert first.items is not second.items and first.items is not value
    assert model.model_fields["items"].default_factory is not None
    assert first.model_fields_set == set()
    if isinstance(first.items, dict):
        first.items["a"].append(2)
        assert value["a"] == second.items["a"] == [1]
    explicit = object()
    assert model(items=explicit).items is explicit


def test_copied_defaults_preserve_alias_merging_and_provenance() -> None:
    """Copy factories contribute static templates to aliased settings merging."""

    default = {"kept": HashableList([1]), "replaced": [2]}

    class Target:
        def __init__(
            self, items: Annotated[dict[str, Any], Field(alias="payload")] = default
        ) -> None:
            self.items = items

    model = Factory.model_from(Target)

    class Child(model):
        pass

    initial = Child()
    assert initial.model_field_sources["items"] == (ClassDefaultsSource, model)
    assert not initial.model_fields_set
    patched = Child(payload={"replaced": [3]})
    assert patched.items == {"kept": [1], "replaced": [3]}
    assert patched.model_field_sources["items"] == (InitSettingsSource, Child)
    assert patched.model_fields_set == {"items"}
    patched.items["kept"].append(4)
    assert Child().items["kept"] == default["kept"] == [1]


def test_copied_defaults_merge_environment_and_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All settings sources retain partial merging with generated templates."""

    default = {"default": 1}

    class Target:
        def __init__(self, items: dict[str, int] = default) -> None:
            self.items = items

    model = Factory.model_from(Target)

    class Config(model, env_prefix="COPIED_", cli_parse_args=True):
        pass

    monkeypatch.setenv("COPIED_ITEMS", '{"env": 2}')
    assert Config(_cli_parse_args=["--items", '{"cli": 3}']).items == {
        "default": 1,
        "env": 2,
        "cli": 3,
    }


def test_recursive_copied_default_retains_partial_updates() -> None:
    """Copied nested factory templates remain patchable without sharing lists."""

    default = HashableList([1])

    class Service:
        def __init__(self, items: Any = default, count: int = 2) -> None:
            self.items = items
            self.count = count

    service_type = Factory.model_from(Service)
    service = service_type()

    class Target:
        def __init__(self, child: Any = service) -> None:
            self.child = child

    # Use a concrete generated annotation so nested partial-update logic applies.
    Target.__init__.__annotations__["child"] = service_type
    model = Factory.model_from(Target)
    first = model(child={"count": 3})
    second = model()
    first.child.items.append(4)
    assert first.child.count == 3 and second.child.count == 2
    assert second.child.items == service.items == [1]


def test_recursive_generation_copies_hashable_factory_templates() -> None:
    """A nested factory's successful hash must not cause mutable-state sharing."""
    default = HashableList([1])

    class Service:
        def __init__(self, items: Any = default) -> None:
            self.items = items

    service = Service()

    class Target:
        def __init__(self, child: Any = service) -> None:
            self.child = child

    model = Factory.model_from(Target, __recursive__=Service)
    first, second = model(), model()
    first.child.items.append(2)
    assert second.child.items == service.items == [1]
    assert model.model_fields["child"].default_factory is not None


@pytest.mark.parametrize(
    "selector",
    [
        SimpleTarget,
        SimpleTarget | None,
        Optional[SimpleTarget],  # noqa: UP045 - callable typing alias regression
        Annotated[SimpleTarget, "tag"],
        NewType("TargetAlias", SimpleTarget),
    ],
    ids=["class", "union", "optional", "annotated", "newtype"],
)
def test_recursive_annotation_selectors(selector: Any) -> None:
    model = Factory.model_from(ParentTarget, __recursive__=selector)
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


def test_factory_selector_predicate_and_parameterized_types() -> None:
    from confidantic._config._factory_build import _FactoryModelBuilder

    typed = _FactoryModelBuilder(
        Factory, SimpleTarget, instance=None, recursive_selector=list[int]
    )
    assert typed.matches_selector([1, 2])
    assert not typed.matches_selector(["1"])
    calls: list[Any] = []

    def predicate(value: Any) -> bool:
        calls.append(value)
        return True

    selected = _FactoryModelBuilder(
        Factory, SimpleTarget, instance=None, recursive_selector=predicate
    )
    assert selected.matches_selector(1)
    assert not _FactoryModelBuilder(
        Factory, SimpleTarget, instance=None, recursive_selector=int
    ).matches_selector(None)
    assert not selected.matches_selector(Factory.model_from(SimpleTarget))
    assert not selected.matches_selector(Factory.instance_from(SimpleTarget))
    assert calls == [1]


@pytest.mark.parametrize("legacy_union", [False, True])
def test_recursive_generation_preserves_annotated_union_metadata(
    legacy_union: bool,
) -> None:
    """Constructor metadata and unrelated alternatives survive recursive generation."""
    choice = Union[ServiceBase, str] if legacy_union else ServiceBase | str  # noqa: UP007 - legacy union support
    annotation = Annotated[choice, Field(description="Selected service.")]

    class Target:
        def __init__(self, service: annotation = _DEFAULT_SERVICE) -> None:
            self.service = service

    model = Factory.model_from(Target, __recursive__=ServiceBase)
    assert model.model_fields["service"].description == "Selected service."
    assert isinstance(model().model_resolve().service, Service)
    assert model(service="fallback").model_resolve().service == "fallback"
