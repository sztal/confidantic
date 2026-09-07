"""Tests for constructor-derived generic factory configuration models."""

import sys
from types import ModuleType
from typing import Any, ForwardRef

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from confidantic import BaseConfig, Factory, FactoryField

_UNTYPED_DEFAULT = object()


class Product:
    """Target with representative constructor parameter kinds."""

    def __init__(
        self,
        count: int,
        label: str = "default",
        untyped: Any = _UNTYPED_DEFAULT,
        *args: Any,
        enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        self.count = count
        self.label = label
        self.untyped = untyped
        self.args = args
        self.enabled = enabled
        self.kwargs = kwargs


Product.__init__.__annotations__.pop("untyped")


def _build_product() -> Product:
    """Build a product for FactoryField call directive tests."""
    return Product(7, "called", enabled=False)


class Basket:
    """Target with mutable constructor attributes."""

    def __init__(self, items: list[str], metadata: dict[str, int]) -> None:
        self.items = items
        self.metadata = metadata


class Child:
    """Nested materialization target."""

    def __init__(self, value: int | None = None) -> None:
        self.value = value


class ServiceBase:
    """Base type for selector matching tests."""


class Service(ServiceBase):
    """Concrete service used as a nested factory source."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


_DEFAULT_SERVICE = Service()


class ServiceHolder:
    """Target with a concrete nested service default."""

    def __init__(
        self, service: ServiceBase = _DEFAULT_SERVICE, label: str = "holder"
    ) -> None:
        self.service = service
        self.label = label


class OptionalServiceHolder:
    """Target with an optional concrete nested service default."""

    def __init__(self, service: ServiceBase | None = None) -> None:
        self.service = service


class RequiredServiceHolder:
    """Target with a required service field."""

    def __init__(self, service: ServiceBase) -> None:
        self.service = service


class ProductModel(BaseModel):
    """Model containing a typed product factory."""

    factory: FactoryField[Product]


def test_model_from_type_returns_typed_factory() -> None:
    """Target types produce classes accepted by typed factory fields."""

    factory = ProductModel(factory=Factory.model_from(Product)).factory

    assert factory.factory_target is Product


def test_factory_field_accepts_runtime_shortcuts() -> None:
    """Factory fields convert target classes, instances, and import strings."""

    class Model(BaseModel):
        factory: FactoryField[Product]

    source = Product(3, "source", enabled=False)

    assert Model(factory=Product).factory.factory_target is Product
    assert (
        Model(factory="tests.test_config_factory:Product").factory.factory_target
        is Product
    )
    product = Model(factory=source).factory().model_resolve()
    assert (product.count, product.label, product.enabled) == (3, "source", False)


@pytest.mark.parametrize(
    "value",
    [
        _build_product,
        "tests.test_config_factory:_build_product",
        {"@call": "tests.test_config_factory:_build_product"},
        {
            "@call": "tests.test_config_factory:Product",
            "count": {"@call": "builtins:int", "@args": ["7"]},
            "label": "called",
            "enabled": False,
        },
    ],
)
def test_factory_field_accepts_call_and_make_inputs(value: Any) -> None:
    """Factory fields evaluate callables and recursive call mappings."""

    class Model(BaseModel):
        factory: FactoryField[Product]

    product = Model(factory=value).factory().model_resolve()
    assert (product.count, product.label, product.enabled) == (7, "called", False)


def test_model_from_instance_returns_typed_factory() -> None:
    """Target instances produce typed factories with derived defaults."""
    source = Product(3, "source", enabled=False)

    factory = ProductModel(factory=Factory.model_from(source)).factory

    assert factory.factory_target is Product
    product = factory().model_resolve()
    assert (product.count, product.label, product.enabled) == (3, "source", False)


def test_instance_from_uses_source_defaults_and_keyword_overrides() -> None:
    """Factory instances combine source-derived defaults with overrides."""
    source = Product(3, "source", enabled=False)

    factory = Factory.instance_from(source, count=4)

    assert factory.factory_target is Product
    assert factory.model_dump() == {
        "count": 4,
        "label": "source",
        "enabled": False,
    }
    product = factory.model_resolve()
    assert (product.count, product.label, product.enabled) == (4, "source", False)


def test_typed_factory_field_preserves_factory_type() -> None:
    """Typed factory fields preserve an already-generated factory type."""
    factory_type = Factory.model_from(Product)

    assert (
        ProductModel.model_validate({"factory": factory_type}).factory is factory_type
    )


def test_typed_factory_field_rejects_factory_instances() -> None:
    """Factory class fields reject factory instances."""
    factory_type = Factory.model_from(Child)

    with pytest.raises(ValidationError):
        ProductModel.model_validate({"factory": factory_type()})


def test_factory_field_composes_with_containers_and_unions() -> None:
    """Generic factory validation composes with standard Pydantic annotations."""

    class Model(BaseModel):
        factories: list[FactoryField[Child]]
        optional: FactoryField[Child] | None
        choice: FactoryField[Child] | str

    model = Model.model_validate(
        {
            "factories": [Factory.model_from(Child)],
            "optional": Factory.model_from(Child),
            "choice": "unchanged",
        }
    )

    assert model.factories[0].factory_target is Child
    assert model.optional is not None
    assert model.optional.factory_target is Child
    assert model.choice == "unchanged"


def test_factory_field_failure_allows_union_fallback() -> None:
    """A mismatched target lets a union's following branch validate it."""

    class PositionalTarget:
        def __init__(self, value: int, /) -> None:
            self.value = value

    class Model(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        factory: FactoryField[Product] | PositionalTarget

    assert isinstance(Model(factory=PositionalTarget(12)).factory, PositionalTarget)


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
        "tests.test_config_factory:Product"
    )


def test_model_from_as_factory_wraps_matching_defaults() -> None:
    """Matching defaults become recursively resolvable factory fields."""
    config_type = Factory.model_from(ServiceHolder, as_factory=ServiceBase)

    service = config_type().service

    assert service.factory_target is Service
    assert config_type().model_resolve().service.value == 1


def test_model_from_as_factory_accepts_type_hints_and_predicates() -> None:
    """Type hints and callable selectors use the concrete default value."""
    type_hint_config = Factory.model_from(ServiceHolder, as_factory=ServiceBase | None)
    predicate_config = Factory.model_from(
        ServiceHolder, as_factory=lambda value: isinstance(value, Service)
    )

    assert type_hint_config().service.factory_target is Service
    assert predicate_config().service.factory_target is Service
    assert predicate_config.model_fields["label"].annotation is str


def test_model_from_as_factory_predicate_leaves_nonmatching_defaults() -> None:
    """A predicate selector leaves nonmatching concrete defaults unchanged."""
    config_type = Factory.model_from(
        ServiceHolder, as_factory=lambda value: isinstance(value, str)
    )

    assert config_type().service is _DEFAULT_SERVICE


def test_model_from_as_factory_handles_none_union_defaults() -> None:
    """Type-hint selectors support optional defaults that do not match."""
    config_type = Factory.model_from(
        OptionalServiceHolder, as_factory=ServiceBase | None
    )

    assert config_type().service is None


def test_model_from_as_factory_uses_instance_values() -> None:
    """Instance sources provide the nested factory's concrete defaults."""
    source = ServiceHolder(Service(7), "configured")

    config_type = Factory.model_from(source, as_factory=ServiceBase)

    assert config_type().model_resolve().service.value == 7
    assert config_type().model_resolve().label == "configured"


def test_model_from_as_factory_wraps_required_instance_values() -> None:
    """Instance values can provide defaults for required constructor fields."""
    config_type = Factory.model_from(
        RequiredServiceHolder(Service(7)), as_factory=ServiceBase
    )

    assert config_type().model_resolve().service.value == 7


def test_model_from_as_factory_leaves_required_fields_unchanged() -> None:
    """Required fields without source values are not auto-generated."""
    config_type = Factory.model_from(RequiredServiceHolder, as_factory=ServiceBase)

    assert config_type.model_fields["service"].is_required()


def test_model_from_as_factory_preserves_existing_factory_defaults() -> None:
    """Existing factory defaults are not wrapped a second time."""
    factory_type = Factory.model_from(Service)

    class Target:
        def __init__(self, service: Factory[ServiceBase] = factory_type) -> None:
            self.service = service

    config_type = Factory.model_from(Target, as_factory=ServiceBase)

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

    config_type = Factory.model_from(MutableServiceHolder, as_factory=MutableService)
    first = config_type()
    second = config_type()

    first.service.values.append(2)

    assert first.service.values == [1, 2]
    assert second.service.values == [1]


def test_model_from_type_accepts_custom_name() -> None:
    """Callers can choose the generated model name."""
    assert (
        Factory.model_from(Product, name="ConfiguredProduct").__name__
        == "ConfiguredProduct"
    )


def test_model_from_resolves_annotations_from_base_class_modules() -> None:
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
    sys.modules[base_module.__name__] = base_module

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


def test_model_resolve_validates_values_and_calls_target() -> None:
    """Resolution passes validated fields to the target constructor."""
    config = Factory.model_from(Product)(count="3", label="configured", enabled=False)

    product = config.model_resolve()

    assert isinstance(product, Product)
    assert product.count == 3
    assert product.label == "configured"
    assert product.enabled is False
    assert config.model_resolve() is not product
    assert not hasattr(config, "materialize")
    assert not callable(config)


def test_model_resolve_overrides_configured_values_with_kwargs() -> None:
    """Resolution keyword arguments override configured values."""
    config = Factory.model_from(Product)(count=3, label="configured", enabled=False)

    product = config.model_resolve(label="overridden", enabled=True)

    assert product.label == "overridden"
    assert product.enabled is True


def test_factory_model_resolve_applies_mapping_before_nested_resolution() -> None:
    """Factory updates are validated before nested factories are resolved."""
    config = Factory.model_from(Product)(count=1)

    product = config.model_resolve({"count": "2"})

    assert product.count == 2


def test_base_config_model_resolve_generates_resolved_model() -> None:
    """BaseConfig resolution replaces Factory fields with target instances."""

    class Config(BaseConfig):
        child: Factory[Child] = Factory.model_from(Child)

    config = Config(child=Factory.model_from(Child)(value=3))

    resolved = config.model_resolve(name="ResolvedConfig")

    assert type(resolved).__name__ == "ResolvedConfig"
    assert type(resolved).model_fields["child"].annotation is Child
    assert isinstance(resolved.child, Child)
    assert resolved.child.value == 3
    assert config.child.value == 3


def test_base_config_model_resolve_resolves_factory_field_classes() -> None:
    """BaseConfig resolution materializes FactoryField class values."""

    class Config(BaseConfig):
        child: FactoryField[Child] = Factory.model_from(Child)

    resolved = Config().model_resolve()

    assert type(resolved).model_fields["child"].annotation is Child
    assert isinstance(resolved.child, Child)


def test_model_resolve_preserves_nested_model_extra_values() -> None:
    """Nested model extras survive factory resolution alongside resolved fields."""

    class Payload(BaseModel):
        model_config = ConfigDict(
            arbitrary_types_allowed=True,
            extra="allow",
        )

        child: Factory[Child]

    class Parent:
        def __init__(self, payload: Payload) -> None:
            self.payload = payload

    payload = Payload(child=Factory.model_from(Child)(value=7), label="extra")
    resolved = Factory.model_from(Parent)(payload=payload).model_resolve()

    assert isinstance(resolved.payload.child, Child)
    assert resolved.payload.child.value == 7
    assert resolved.payload.model_extra == {"label": "extra"}


def test_base_config_model_resolve_preserves_nested_factory_when_not_recursive() -> (
    None
):
    """Factory resolution can leave nested factories in the target intact."""

    class Parent:
        def __init__(self, child: Factory[Child]) -> None:
            self.child = child

    class Config(BaseConfig):
        parent: Factory[Parent] = Factory.model_from(Parent)

    child_config = Factory.model_from(Child)(value=4)
    config = Config(parent=Factory.model_from(Parent)(child=child_config))

    resolved = config.model_resolve(recursive=False)

    assert isinstance(resolved.parent, Parent)
    assert resolved.parent.child is child_config


def test_base_config_model_resolve_without_factories_returns_shallow_copy() -> None:
    """Models without factories do not receive a generated resolved class."""

    class Config(BaseConfig):
        value: int

    config = Config(value=1)

    resolved = config.model_resolve()

    assert type(resolved) is Config
    assert resolved is not config
    assert resolved.value == 1


def test_model_resolve_resolves_nested_factory_configs() -> None:
    """Direct resolution recursively resolves nested factories."""

    class Parent:
        def __init__(
            self, child: Factory[Child], children: list[Factory[Child]]
        ) -> None:
            self.child = child
            self.children = children

    child_config = Factory.model_from(Child)
    parent = Factory.model_from(Parent)(
        child=child_config(value=1),
        children=[child_config(value=2), child_config(value=3)],
    ).model_resolve()

    assert isinstance(parent.child, Child)
    assert [child.value for child in parent.children] == [2, 3]


def test_model_resolve_resolves_nested_factories_in_containers() -> None:
    """Nested factories are resolved in mappings and immutable containers."""

    class Parent:
        def __init__(
            self,
            mapping: dict[str, Any],
            tuple_value: tuple[Any, ...],
            set_value: set[Any],
            frozenset_value: frozenset[Any],
        ) -> None:
            self.mapping = mapping
            self.tuple_value = tuple_value
            self.set_value = set_value
            self.frozenset_value = frozenset_value

    child_config = Factory.model_from(Child)
    parent = (
        Factory.model_from(Parent)
        .model_construct(
            mapping={"child": child_config(value=1)},
            tuple_value=(child_config(value=2),),
            set_value={child_config(value=3)},
            frozenset_value=frozenset({child_config(value=4)}),
        )
        .model_resolve()
    )

    assert parent.mapping["child"].value == 1
    assert parent.tuple_value[0].value == 2
    assert {child.value for child in parent.set_value} == {3}
    assert {child.value for child in parent.frozenset_value} == {4}


def test_factory_accepts_nested_factories_in_set_inputs() -> None:
    """Validated factory configs can be supplied in set-valued inputs."""

    class Parent:
        def __init__(
            self,
            children: set[Factory[Child]],
            frozen_children: frozenset[Factory[Child]],
        ) -> None:
            self.children = children
            self.frozen_children = frozen_children

    child_config = Factory.model_from(Child)
    config = Factory.model_from(Parent)(
        children={child_config(value=1)},
        frozen_children=frozenset({child_config(value=2)}),
    )

    parent = config.model_resolve()

    assert {child.value for child in parent.children} == {1}
    assert {child.value for child in parent.frozen_children} == {2}


def test_model_resolve_rejects_cyclic_values() -> None:
    """Cyclic nested values cannot be recursively resolved."""

    class Parent:
        def __init__(self, payload: Any) -> None:
            self.payload = payload

    payload: list[Any] = []
    payload.append(payload)
    config = Factory.model_from(Parent).model_construct(payload=payload)

    with pytest.raises(ValueError, match="cyclic values cannot be resolved"):
        config.model_resolve()


def test_factory_default_target_class_is_converted() -> None:
    """A generated factory class can be used as a typed default."""
    config_type = create_model(
        "Config",
        __base__=BaseConfig,
        service=(FactoryField[Child], Factory.model_from(Child)),
    )

    assert config_type().service.factory_target is Child


def test_factory_default_factory_class_is_preserved() -> None:
    """A concrete factory class default is preserved without regeneration."""

    factory_type = Factory.model_from(Child)

    class Config(BaseConfig):
        service: FactoryField[Child] = factory_type

    service = Config().service

    assert service is factory_type


def test_factory_instance_default_is_rejected() -> None:
    """Factory instances are rejected because fields store factory types."""

    class Config(BaseConfig):
        service: FactoryField[Child] = Factory.instance_from(Child)  # type: ignore[assignment]

    with pytest.raises(ValidationError):
        Config()


def test_factory_field_accepts_a_factory_for_a_target_subclass() -> None:
    """Typed factory fields accept factories for compatible target subclasses."""

    class Parent:
        pass

    class ChildTarget(Parent):
        def __init__(self, value: int = 1) -> None:
            self.value = value

    class Config(BaseModel):
        service: FactoryField[Parent]

    factory_type = Factory.model_from(ChildTarget(value=2))
    config = Config(service=factory_type)

    assert config.service is factory_type
    assert isinstance(config.service().model_resolve().value, int)
    assert config.service().model_resolve().value == 2


def test_factory_field_rejects_a_factory_for_another_target() -> None:
    """Typed factory fields reject concrete factories for another target."""

    class Other:
        def __init__(self, name: str = "other") -> None:
            self.name = name

    class Config(BaseModel):
        service: FactoryField[Child]

    other = Factory.model_from(Other)

    with pytest.raises(ValidationError):
        Config(service=other)


def test_factory_field_rejects_a_target_class_for_another_target() -> None:
    """Typed factory fields reject target classes of another type."""

    class Other:
        def __init__(self, name: str = "other") -> None:
            self.name = name

    class Config(BaseModel):
        service: FactoryField[Child]

    with pytest.raises(ValidationError):
        Config(service=Other)


def test_factory_default_factory_is_converted() -> None:
    """Normal Pydantic default factories remain supported."""

    class Config(BaseConfig):
        service: FactoryField[Child] = Field(
            default_factory=lambda: Factory.model_from(Child)
        )

    assert Config().service.factory_target is Child


def test_model_resolve_disables_cli_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target construction cannot consume process command-line arguments."""

    class CliConfig(BaseConfig, cli_parse_args=True):
        value: int = 1

    class Target:
        def __init__(self) -> None:
            self.config = CliConfig()

    monkeypatch.setattr(sys, "argv", ["factory.py", "--value=17"])

    assert Factory.model_from(Target)().model_resolve().config.value == 1


def test_invalid_factory_input_reports_validation_error() -> None:
    """Factory validation exposes an ordinary Pydantic validation error."""
    with pytest.raises(ValidationError, match="Factory"):
        ProductModel.model_validate({"factory": object()})
