"""Tests for constructor-derived generic factory configuration models."""

import sys
from types import ModuleType
from typing import Any, ForwardRef

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from confidantic import BaseConfig, Factory

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


class Basket:
    """Target with mutable constructor attributes."""

    def __init__(self, items: list[str], metadata: dict[str, int]) -> None:
        self.items = items
        self.metadata = metadata


class Child:
    """Nested materialization target."""

    def __init__(self, value: int | None = None) -> None:
        self.value = value


class ProductModel(BaseModel):
    """Model containing a typed product factory."""

    factory: Factory[Product]


def test_factory_field_converts_target_instance() -> None:
    """Typed Pydantic fields convert a target instance to a factory."""
    source = Product(3, "source", enabled=False)

    factory = ProductModel.model_validate({"factory": source}).factory

    assert isinstance(factory, Factory)
    assert factory.model_dump() == {"count": 3, "label": "source", "enabled": False}
    assert isinstance(factory.materialize(), Product)


def test_factory_field_validates_mapping() -> None:
    """Mappings use the generated target factory fields for validation."""
    factory = ProductModel.model_validate(
        {"factory": {"count": "5", "label": "configured"}}
    ).factory

    assert factory.count == 5
    assert factory.label == "configured"


def test_factory_field_converts_assignment() -> None:
    """Assignment validation applies the generic factory conversion."""

    class Model(BaseModel):
        model_config = ConfigDict(validate_assignment=True)

        factory: Factory[Child]

    model = Model(factory=Child(10))
    model.factory = Child(11)

    assert model.factory.materialize().value == 11


def test_factory_field_composes_with_containers_and_unions() -> None:
    """Generic factory validation composes with standard Pydantic annotations."""

    class Model(BaseModel):
        factories: list[Factory[Child]]
        optional: Factory[Child] | None
        choice: Factory[Child] | str

    model = Model.model_validate(
        {
            "factories": [Child(8)],
            "optional": Child(9),
            "choice": "unchanged",
        }
    )

    assert model.factories[0].materialize().value == 8
    assert model.optional is not None
    assert model.optional.materialize().value == 9
    assert model.choice == "unchanged"


def test_factory_field_failure_allows_union_fallback() -> None:
    """A mismatched target lets a union's following branch validate it."""

    class PositionalTarget:
        def __init__(self, value: int, /) -> None:
            self.value = value

    class Model(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        factory: Factory[Product] | PositionalTarget

    assert isinstance(Model(factory=PositionalTarget(12)).factory, PositionalTarget)


def test_model_from_type_creates_typed_config_fields() -> None:
    """Constructor annotations define fields on the generated generic factory."""
    config_type = Factory.model_from(Product)

    assert config_type.__name__ == "ProductConfig"
    assert config_type.__module__ == Product.__module__
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


def test_materialize_validates_values_and_calls_target() -> None:
    """Materialization passes validated fields to the target constructor."""
    config = Factory.model_from(Product)(count="3", label="configured", enabled=False)

    product = config.materialize()

    assert isinstance(product, Product)
    assert product.count == 3
    assert product.label == "configured"
    assert product.enabled is False
    assert config() is not product
    assert Factory.__call__ is Factory.materialize


def test_materialize_overrides_configured_values_with_kwargs() -> None:
    """Materialization keyword arguments override configured values."""
    config = Factory.model_from(Product)(count=3, label="configured", enabled=False)

    product = config.materialize(label="overridden", enabled=True)

    assert product.label == "overridden"
    assert product.enabled is True


def test_materialize_resolves_nested_factory_configs() -> None:
    """Direct materialization recursively materializes nested factories."""

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
    ).materialize()

    assert isinstance(parent.child, Child)
    assert [child.value for child in parent.children] == [2, 3]


def test_materialize_resolves_nested_factories_in_containers() -> None:
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
        .materialize()
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

    parent = config.materialize()

    assert {child.value for child in parent.children} == {1}
    assert {child.value for child in parent.frozen_children} == {2}


def test_materialize_rejects_cyclic_values() -> None:
    """Cyclic nested values cannot be recursively materialized."""

    class Parent:
        def __init__(self, payload: Any) -> None:
            self.payload = payload

    payload: list[Any] = []
    payload.append(payload)
    config = Factory.model_from(Parent).model_construct(payload=payload)

    with pytest.raises(ValueError, match="cyclic values cannot be resolved"):
        config.materialize()


def test_factory_default_target_class_is_converted() -> None:
    """A target class default is converted through the typed factory schema."""
    config_type = create_model(
        "Config",
        __base__=BaseConfig,
        service=(Factory[Child], Child),
    )

    assert config_type().service.materialize().value is None


def test_factory_instance_default_is_type_safe() -> None:
    """Factory instances provide a type-safe default for annotated fields."""

    class Config(BaseConfig):
        service: Factory[Child] = Factory[Child].instance_from(Child)

    assert Config().service.materialize().value is None


def test_factory_default_factory_is_converted() -> None:
    """Normal Pydantic default factories remain supported."""

    class Config(BaseConfig):
        service: Factory[Child] = Field(
            default_factory=lambda: Factory[Child].instance_from(Child, value=4)
        )

    assert Config().service.materialize().value == 4


def test_materialize_disables_cli_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target construction cannot consume process command-line arguments."""

    class CliConfig(BaseConfig, cli_parse_args=True):
        value: int = 1

    class Target:
        def __init__(self) -> None:
            self.config = CliConfig()

    monkeypatch.setattr(sys, "argv", ["factory.py", "--value=17"])

    assert Factory.model_from(Target)().materialize().config.value == 1


def test_model_resolve_is_not_available() -> None:
    """Whole-model factory materialization is intentionally unsupported."""
    assert not hasattr(BaseConfig, "model_resolve")


def test_invalid_factory_input_reports_validation_error() -> None:
    """Factory validation exposes an ordinary Pydantic validation error."""
    with pytest.raises(ValidationError, match="Factory"):
        ProductModel.model_validate({"factory": object()})
