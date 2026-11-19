"""Constructor inspection, recursive field generation, and copied defaults."""

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Annotated, Any, ForwardRef, NewType, Optional, Union

import pytest
from pydantic import Field, TypeAdapter, ValidationError, create_model
from pydantic.errors import PydanticUserError
from pydantic_settings import InitSettingsSource
from typing_extensions import TypedDict

from confidantic import BaseConfig, ClassDefaultsSource, Factory
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


@pytest.fixture
def annotation_target(monkeypatch: pytest.MonkeyPatch) -> Callable[..., type[Any]]:
    """Create isolated targets with symbolic annotations and real module globals."""

    def make_target(source: str, *, postponed: bool = True) -> type[Any]:
        module = ModuleType("factory_annotation_target")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        prefix = "from __future__ import annotations\n" if postponed else ""
        exec(prefix + source, vars(module))
        return module.Target

    return make_target


@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize("from_instance", [False, True])
def test_factory_annotation_policy(
    annotation_target: Callable[..., type[Any]], inherited: bool, from_instance: bool
) -> None:
    """Permissive fields retain requiredness, defaults, and independently typed fields."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n    from pathlib import Path\n"
        "class Target:\n"
        "    def __init__(self, path: Path, count: int = 1, extra=None):\n"
        "        self.path, self.count, self.extra = path, count, extra\n"
    )
    if inherited:
        source += "class Target(Target):\n    pass\n"
    target = annotation_target(source)
    template = target("original", extra=[1]) if from_instance else target
    with pytest.raises(
        NameError, match=r"Target.__init__ parameter 'path'.*Path"
    ) as error:
        Factory.model_from(template)
    assert isinstance(error.value.__cause__, NameError)
    assert error.value.name == "Path"

    model = Factory.model_from(template, __strict__=False)
    assert model.__pydantic_complete__
    assert model.factory_fields == ("path", "count", "extra")
    assert model.model_fields["path"].annotation is Any
    assert model.model_fields["extra"].annotation is Any
    assert model.model_fields["path"].is_required() is not from_instance
    config = model(path="unchanged", count="2")
    assert config.path == "unchanged"
    assert config.model_resolve().count == 2
    with pytest.raises(ValidationError):
        model(path="x", count="invalid")
    with pytest.raises(ValidationError):
        model.model_validate({"path": "x", "count": "2"}, strict=True)
    if from_instance:
        first, second = model(), model()
        first.extra.append(2)
        assert second.extra == [1]
    else:
        with pytest.raises(ValidationError):
            model()
    assert "type" not in model.model_json_schema()["properties"]["path"]
    assert not any(name.startswith("_factory") for name in config.model_dump())
    with pytest.raises(NameError):
        Factory.model_from(template)


@pytest.mark.parametrize("permissive_first", [False, True])
def test_factory_namespaces_are_isolated(
    annotation_target: Callable[..., type[Any]], permissive_first: bool
) -> None:
    """Cached generic bases never retain a generation call's namespace or fallback."""
    target = annotation_target(
        "class Target:\n"
        "    def __init__(self, value: Missing, other: float = 1):\n"
        "        self.value, self.other = value, other\n"
    )
    if permissive_first:
        permissive = Factory.model_from(target, __strict__=False)
    namespace = {"Missing": int}
    integers = Factory.model_from(target, __types_namespace__=namespace)
    namespace["Missing"] = str
    strings = Factory.model_from(target, __types_namespace__=namespace)
    if not permissive_first:
        permissive = Factory.model_from(target, __strict__=False)
    assert integers(value="2", other="3").value == 2
    assert strings(value="2").value == "2"
    assert permissive.model_fields["value"].annotation is Any
    assert integers._factory_types_namespace == {"Missing": int}
    assert "Missing" not in target.__init__.__globals__
    assert issubclass(integers, Factory[target])
    with pytest.raises(NameError):
        Factory.model_from(target)
    with pytest.raises(NameError):
        TypeAdapter(Factory[target]).validate_python({"value": 1})
    assert integers(value="4").value == 4


def test_namespace_priority_and_concrete_annotations(
    annotation_target: Callable[..., type[Any]],
) -> None:
    """Explicit symbols override globals, retaining extras and already evaluated types."""
    target = annotation_target(
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "Item = str\n"
        "class Target:\n"
        "    def __init__(self, value: list[Item], count: Annotated[Item, Field(gt=0)], other: float = 'default'):\n"
        "        self.value, self.count, self.other = value, count, other\n"
    )
    # An explicit concrete annotation has no symbolic names left to override.
    target.__init__.__annotations__["other"] = str
    model = Factory.model_from(target, __types_namespace__={"Item": int, "str": int})
    assert model(value=["2"], count="3", other="text").model_dump() == {
        "value": [2],
        "count": 3,
        "other": "text",
    }
    with pytest.raises(ValidationError):
        model(value=[1], count=0, other="text")
    assert target.__init__.__globals__["Item"] is str


@pytest.mark.parametrize("annotation", ["Missing", "list[Missing]", "int | Missing"])
def test_unresolved_annotation_falls_back_as_a_whole(
    annotation_target: Callable[..., type[Any]], annotation: str
) -> None:
    """Only the unresolved field loses validation, including nested missing names."""
    target = annotation_target(
        f"class Target:\n    def __init__(self, value: {annotation}):\n        self.value = value\n"
    )
    config = Factory.instance_from(target, __strict__=False, value={"raw": "value"})
    assert type(config).model_fields["value"].annotation is Any
    assert config.model_resolve().value == {"raw": "value"}
    typed = Factory.instance_from(
        target,
        __types_namespace__={"Missing": int},
        value=["2"] if annotation.startswith("list") else "2",
    )
    assert typed.value == ([2] if annotation.startswith("list") else 2)


@pytest.mark.parametrize("strict", [False, True])
def test_irrelevant_annotations_do_not_block_fields(
    annotation_target: Callable[..., type[Any]], strict: bool
) -> None:
    """Return and variadic names are not needed to build keyword fields."""
    target = annotation_target(
        "class Target:\n"
        "    def __init__(self, value: int = 1, *args: MissingArgs, **kwargs: MissingKwargs) -> MissingReturn:\n"
        "        self.value = value\n"
    )
    model = Factory.model_from(target, __strict__=strict)
    assert model.factory_fields == ("value",)
    assert model(value="2").model_resolve().value == 2


@pytest.mark.parametrize("annotated", [False, True])
def test_permissive_positional_only_is_rejected(
    annotation_target: Callable[..., type[Any]], annotated: bool
) -> None:
    """Permissive mode cannot turn positional-only inputs into keyword fields."""
    annotation = ": Missing" if annotated else ""
    target = annotation_target(
        f"class Target:\n    def __init__(self, value{annotation} = 1, /):\n        self.value = value\n"
    )
    with pytest.raises(TypeError, match="positional-only"):
        Factory.model_from(target, __strict__=False)
    if not annotated:
        assert Factory.model_from(target).factory_fields == ()


@pytest.mark.parametrize(
    "annotation, error", [("int | 42", TypeError), ("'list['", SyntaxError)]
)
def test_permissive_mode_preserves_annotation_errors(
    annotation_target: Callable[..., type[Any]], annotation: str, error: type[Exception]
) -> None:
    """Malformed annotations are not treated as unresolved names."""
    target = annotation_target(
        f"class Target:\n    def __init__(self, value: {annotation}):\n        self.value = value\n"
    )
    with pytest.raises(error):
        Factory.model_from(target, __strict__=False)


def test_permissive_mode_preserves_schema_errors(
    annotation_target: Callable[..., type[Any]],
) -> None:
    """Concrete factories still build schemas eagerly with deferred generic bases."""
    target = annotation_target(
        "from pydantic import PydanticUserError\n"
        "class Unsupported:\n"
        "    @classmethod\n"
        "    def __get_pydantic_core_schema__(cls, source, handler):\n"
        "        raise PydanticUserError('bad schema', code='invalid-schema')\n"
        "class Target:\n"
        "    def __init__(self, value: Unsupported):\n        self.value = value\n"
    )
    with pytest.raises(PydanticUserError, match="bad schema"):
        Factory.model_from(target, __strict__=False)


@pytest.mark.parametrize("strict", [False, True])
def test_annotation_options_follow_recursive_generation(
    annotation_target: Callable[..., type[Any]], strict: bool
) -> None:
    """Nested generation receives namespace overrides and the fallback policy."""
    target = annotation_target(
        "class Child:\n"
        "    def __init__(self, value: Missing = 1, extra=None):\n"
        "        self.value, self.extra = value, extra\n"
        "class Target:\n"
        "    def __init__(self, child: Child = Child()):\n        self.child = child\n"
    )
    namespace = {"Missing": int} if strict else {}
    model = Factory.model_from(
        target,
        __recursive__=lambda value: hasattr(value, "value"),
        __strict__=strict,
        __types_namespace__=namespace,
    )
    config = model(child={"value": "2"})
    assert config.model_resolve().child.value == (2 if strict else "2")
    assert ("extra" in type(config.child).model_fields) is not strict


@pytest.mark.parametrize("strict", [False, True])
def test_generated_models_retain_annotation_policy(
    annotation_target: Callable[..., type[Any]], strict: bool
) -> None:
    """Subclasses, rebuilds, and validation-time target conversion retain policy."""
    target = annotation_target(
        "class Target:\n"
        "    def __init__(self, value: Missing = 1, extra=None):\n"
        "        self.value, self.extra = value, extra\n"
    )
    namespace = {"Missing": int} if strict else {}
    generated = Factory.model_from(
        target, __strict__=strict, __types_namespace__=namespace
    )

    class Derived(generated):
        pass

    Derived.model_rebuild(force=True)
    container = create_model("Container", __base__=BaseConfig, target=(Derived, ...))
    result = container(target={"value": "2"})
    assert result.model_resolve().target.value == (2 if strict else "2")
    for model in (generated, Derived):
        adapter = TypeAdapter(model)
        converted = adapter.validate_python(target(3 if strict else "3"))
        assert converted.model_resolve().value == (3 if strict else "3")
        converted_class = adapter.validate_python(target)
        assert converted_class(value="4").model_resolve().value == (
            4 if strict else "4"
        )
        with pytest.raises(NameError):
            model.model_from(target)


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="native deferred annotations require Python 3.14"
)
def test_native_deferred_annotations(
    annotation_target: Callable[..., type[Any]],
) -> None:
    """Native lazy annotations allow missing fields and ignored return names."""
    target = annotation_target(
        "class Target:\n"
        "    def __init__(self, value: Missing, count: int = 1) -> MissingReturn:\n"
        "        self.value, self.count = value, count\n",
        postponed=False,
    )
    assert (
        Factory.instance_from(target, __strict__=False, value="2", count="3").count == 3
    )
    assert (
        Factory.instance_from(
            target, __types_namespace__={"Missing": int}, value="2"
        ).value
        == 2
    )
    with pytest.raises(NameError, match="parameter 'value'"):
        Factory.model_from(target)


def test_unannotated_required_field_is_included_only_in_permissive_mode() -> None:
    """Untyped required inputs become required Any fields only on explicit opt-in."""

    class Target:
        def __init__(self, value: Any) -> None:
            self.value = value

    Target.__init__.__annotations__.pop("value")
    assert Factory.model_from(Target).factory_fields == ()
    model = Factory.model_from(Target, __strict__=False)
    with pytest.raises(ValidationError):
        model()
    value = object()
    assert model(value=value).model_resolve().value is value


def test_explicit_forward_refs_do_not_cache_namespace_overrides() -> None:
    """Each call re-evaluates shared ForwardRef objects, including on older Python."""

    class Target:
        def __init__(self, value: Any) -> None:
            self.value = value

    Target.__init__.__annotations__["value"] = ForwardRef("Payload")
    integers = Factory.model_from(Target, __types_namespace__={"Payload": int})
    strings = Factory.model_from(Target, __types_namespace__={"Payload": str})
    assert integers(value="2").value == 2
    assert strings(value="2").value == "2"


def test_no_type_check_annotations_remain_untyped() -> None:
    """Per-field resolution respects the constructor's no_type_check marker."""
    from typing import no_type_check

    class Target:
        @no_type_check
        def __init__(self, value: int) -> None:
            self.value = value

    assert Factory.model_from(Target).factory_fields == ()
    model = Factory.model_from(Target, __strict__=False)
    assert model.model_fields["value"].annotation is Any
    assert model(value="text").model_resolve().value == "text"
