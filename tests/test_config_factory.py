"""Tests for constructor-derived factory configuration models."""

import sys
from typing import Annotated, Any, cast, get_args

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.fields import FieldInfo

from confidantic import BaseConfig, FactoryConfig, SettingsConfigDict


class Product:
    """Target with representative constructor parameter kinds."""

    def __init__(
        self,
        count: int,
        label: str = "default",
        *args: Any,
        enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        self.count = count
        self.label = label
        self.args = args
        self.enabled = enabled
        self.kwargs = kwargs


class Basket:
    """Target with a mutable constructor value exposed as an attribute."""

    def __init__(self, items: list[str], metadata: dict[str, int]) -> None:
        self.items = items
        self.metadata = metadata


class Child:
    """Nested materialization target."""

    def __init__(self, value: int) -> None:
        self.value = value


class ChildConfig(FactoryConfig):
    """Concrete factory config used in statically typed resolution tests."""

    factory_target = Child
    factory_fields = ("value",)

    value: int


class NestedModel(BaseModel):
    """Plain Pydantic model containing a concrete factory config."""

    child: ChildConfig


class ResolvableConfig(BaseConfig):
    """Configuration exercising recursive factory resolution."""

    model_config = SettingsConfigDict(frozen=True)

    primary: ChildConfig = Field(
        default_factory=lambda: ChildConfig(value=1),
        alias="PRIMARY",
        description="Primary child factory.",
    )
    optional: ChildConfig | None = None
    choice: ChildConfig | str = "unconfigured"
    annotated: Annotated[ChildConfig, Field(description="Annotated child.")] = Field(
        default_factory=lambda: ChildConfig(value=2)
    )
    mapping: dict[str, ChildConfig] = Field(default_factory=dict)
    keyed: dict[ChildConfig, str] = Field(default_factory=dict)
    sequence: list[ChildConfig] = Field(default_factory=list)
    fixed: tuple[ChildConfig, ...] = ()
    unique: set[ChildConfig] = Field(default_factory=set)
    frozen_unique: frozenset[ChildConfig] = frozenset()
    nested: NestedModel = Field(
        default_factory=lambda: NestedModel(child=ChildConfig(value=3))
    )
    label: str = "default"

    @field_validator("label")
    @classmethod
    def add_marker(cls, value: str) -> str:
        return f"{value}!"

    def primary_value(self) -> int:
        """Return the selected primary value."""
        return self.primary.value


def test_factory_field_converts_target_instance() -> None:
    """Pydantic fields convert target instances into factory configs."""

    class Model(BaseModel):
        factory: FactoryConfig

    source = Product(3, "source", enabled=False)
    model = Model.model_validate({"factory": source})

    assert isinstance(model.factory, FactoryConfig)
    assert model.factory.model_dump() == {
        "count": 3,
        "label": "source",
        "enabled": False,
    }
    assert isinstance(model.factory.materialize(), Product)


def test_concrete_factory_field_converts_target_instance() -> None:
    """Concrete factory fields generate compatible config subclasses."""
    model = NestedModel.model_validate({"child": Child(4)})

    assert isinstance(model.child, ChildConfig)
    assert model.child.value == 4
    assert isinstance(model.child.materialize(), Child)


def test_concrete_factory_field_validates_mapping() -> None:
    """Mappings retain normal concrete model validation."""
    model = NestedModel.model_validate({"child": {"value": "5"}})

    assert type(model.child) is ChildConfig
    assert model.child.value == 5


def test_factory_field_preserves_existing_config_instance() -> None:
    """Existing factory configs bypass conversion and subtype enforcement."""

    class Model(BaseModel):
        factory: FactoryConfig

    child = ChildConfig(value=6)
    bare = Model.model_validate({"factory": child})
    product_config = cast(Any, FactoryConfig.model_from(Product))(count=7)
    concrete = NestedModel.model_validate({"child": product_config})

    assert bare.factory is child
    assert concrete.child is product_config


def test_factory_field_validation_composes_with_annotations() -> None:
    """Factory conversion composes with containers, optionals, and unions."""

    class Model(BaseModel):
        factories: list[FactoryConfig]
        optional: FactoryConfig | None
        choice: FactoryConfig | str

    model = Model.model_validate(
        {
            "factories": [Child(8)],
            "optional": Child(9),
            "choice": "unchanged",
        }
    )

    assert isinstance(model.factories[0], FactoryConfig)
    assert model.factories[0].materialize().value == 8
    assert isinstance(model.optional, FactoryConfig)
    assert model.optional.materialize().value == 9
    assert model.choice == "unchanged"


def test_factory_field_converts_assignment() -> None:
    """Assignment validation uses the same factory conversion schema."""

    class Model(BaseModel):
        model_config = ConfigDict(validate_assignment=True)

        factory: FactoryConfig

    model = Model(factory=ChildConfig(value=10))
    cast(Any, model).factory = Child(11)

    assert isinstance(model.factory, FactoryConfig)
    assert model.factory.materialize().value == 11


def test_factory_field_failure_allows_union_fallback() -> None:
    """Factory conversion failures remain local to their union branch."""

    class PositionalTarget:
        def __init__(self, value: int, /) -> None:
            self.value = value

    class FactoryModel(BaseModel):
        factory: FactoryConfig

    class UnionModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        factory: FactoryConfig | PositionalTarget

    source = PositionalTarget(12)

    with pytest.raises(ValidationError, match="FactoryConfig"):
        FactoryModel.model_validate({"factory": source})

    assert UnionModel.model_validate({"factory": source}).factory is source


def test_model_from_type_creates_ordered_config_fields() -> None:
    """Annotated keyword-capable constructor parameters become fields."""
    config_type = cast(Any, FactoryConfig.model_from(Product))

    assert config_type.__name__ == "ProductConfig"
    assert issubclass(config_type, FactoryConfig)
    assert config_type.factory_target is Product
    assert config_type.factory_fields == ("count", "label", "enabled")
    assert tuple(config_type.model_fields) == ("count", "label", "enabled")
    assert config_type.model_fields["count"].is_required()
    assert config_type.model_fields["label"].default == "default"
    assert config_type.model_fields["enabled"].default is True


def test_model_from_rejects_mismatched_init_annotations() -> None:
    """Unannotated constructor parameters cannot be represented by a factory."""

    class UntypedTarget:
        def __init__(self, value: int, label="default") -> None:
            self.value = value
            self.label = label

    with pytest.raises(
        TypeError,
        match=(
            r"UntypedTarget.__init__ type annotations do not match its signature "
            r"\(missing annotations for: label\); cannot create a model factory "
            r"config"
        ),
    ):
        FactoryConfig.model_from(UntypedTarget)


def test_cli_help_omits_generated_factory_attributes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Generated factory fields do not become CLI group descriptions."""

    class Target:
        def __init__(self, value: int = 1) -> None:
            self.value = value

    class Config(BaseConfig, cli_parse_args=True):
        target: FactoryConfig.model_from(Target) = Field(  # type: ignore[valid-type]
            default_factory=Target
        )

    with pytest.raises(SystemExit, match="0"):
        cast(Any, Config)(_cli_parse_args=["--help"])

    output = capsys.readouterr().out
    assert "target options:" in output
    assert "--target.value int" in output
    assert "Attributes" not in output


def test_model_from_type_accepts_custom_name() -> None:
    """Callers can choose the generated model name."""
    config_type = cast(
        Any,
        FactoryConfig.model_from(Product, name="ConfiguredProduct"),
    )

    assert config_type.__name__ == "ConfiguredProduct"


def test_model_from_rejects_annotated_positional_only_parameter() -> None:
    """A config cannot safely represent positional-only target arguments."""

    class PositionalTarget:
        def __init__(self, value: int, /) -> None:
            self.value = value

    with pytest.raises(
        TypeError,
        match=r"PositionalTarget.__init__ parameter 'value' is positional-only",
    ):
        FactoryConfig.model_from(PositionalTarget)


def test_model_from_instance_uses_isolated_attribute_defaults() -> None:
    """Mutable instance attributes are copied for every config instance."""
    source = Basket(["first"], {"count": 1})
    config_type = cast(Any, FactoryConfig.model_from(source))

    first = config_type()
    second = config_type()
    first.items.append("second")
    first.metadata["count"] = 2

    assert first.items == ["first", "second"]
    assert first.metadata == {"count": 2}
    assert second.items == ["first"]
    assert second.metadata == {"count": 1}
    assert source.items == ["first"]
    assert source.metadata == {"count": 1}


def test_model_from_instance_uses_immutable_attribute_defaults() -> None:
    """Immutable instance attributes become generated model defaults."""
    source = Product(4, "source", enabled=False)
    config_type = cast(Any, FactoryConfig.model_from(source))

    assert config_type().model_dump() == {
        "count": 4,
        "label": "source",
        "enabled": False,
    }


def test_model_from_instance_clones_unhashable_attribute_defaults() -> None:
    """Unhashable model attributes are deeply isolated between configs."""

    class Payload(BaseModel):
        value: int

    class PayloadTarget:
        def __init__(self, payload: Payload) -> None:
            self.payload = payload

    source = PayloadTarget(Payload(value=1))
    config_type = cast(Any, FactoryConfig.model_from(source))

    first = config_type()
    second = config_type()
    first.payload.value = 2

    assert first.payload.value == 2
    assert second.payload.value == 1
    assert source.payload.value == 1
    assert first.payload is not second.payload
    assert first.payload is not source.payload


def test_model_factory_wraps_current_values_and_resolves_them() -> None:
    """Selected values define concrete factory annotations and defaults."""

    class Config(BaseConfig):
        product: Product

    product = Product(4, "source", enabled=False)
    source = Config(product=product)

    factory_type = source.model_factory()

    assert factory_type.__name__ == "ConfigFactory"
    assert issubclass(factory_type, Config)
    field = factory_type.model_fields["product"]
    assert issubclass(field.annotation, FactoryConfig)
    assert isinstance(field.default, FactoryConfig)
    assert field.default.model_dump() == {
        "count": 4,
        "label": "source",
        "enabled": False,
    }
    factory = factory_type()
    assert isinstance(factory.product, FactoryConfig)
    assert factory.product.model_dump() == {
        "count": 4,
        "label": "source",
        "enabled": False,
    }
    assert source.product is product
    resolved = factory.model_resolve()
    assert isinstance(resolved.product, Product)
    assert resolved.product.count == 4
    assert resolved.product.label == "source"
    assert resolved.product.enabled is False
    assert factory.model_factory() is factory_type


def test_model_factory_selects_fields_by_name() -> None:
    """One-argument selectors receive names and choose a field subset."""

    class Config(BaseConfig):
        product: Product
        child: Child

    selected: list[str] = []

    def select(field_name: str) -> bool:
        selected.append(field_name)
        return field_name == "child"

    product = Product(1)
    source = Config(product=product, child=Child(2))
    factory_type = source.model_factory(select)
    factory = factory_type(product=product)

    assert selected == ["product", "child"]
    assert factory.product is product
    assert isinstance(factory.child, FactoryConfig)
    assert factory_type.model_fields["product"].annotation is Product


def test_model_factory_selects_fields_by_field_info() -> None:
    """Two-argument selectors receive source field information."""

    class Config(BaseConfig):
        product: Product = Field(description="factorize")
        child: Child = Field(description="retain")

    observed: dict[str, Any] = {}

    def select(field_name: str, field: FieldInfo) -> bool:
        observed[field_name] = field
        return field.description == "factorize"

    source = Config(product=Product(1), child=Child(2))
    factory_type = source.model_factory(select)
    factory = factory_type(child=source.child)

    assert observed == Config.model_fields
    assert isinstance(factory.product, FactoryConfig)
    assert factory.child is source.child
    assert factory_type.model_fields["product"].description == "factorize"


def test_model_factory_controls_inherited_annotation_metadata() -> None:
    """Derived fields clear metadata by default or preserve it on request."""

    class Config(BaseConfig):
        product: Annotated[Product, "marker"] = Field(description="Product.")

    source = Config(product=Product(1))

    cleared_type = source.model_factory()
    preserved_type = source.model_factory(clear_metadata=False)

    source_field = Config.model_fields["product"]
    cleared_field = cleared_type.model_fields["product"]
    preserved_field = preserved_type.model_fields["product"]
    assert source_field.metadata == ["marker"]
    assert cleared_field.metadata == []
    assert preserved_field.metadata == ["marker"]
    assert cleared_field.description == "Product."
    assert preserved_field.description == "Product."
    with pytest.raises(TypeError, match="positional argument"):
        cast(Any, source).model_factory(None, False)


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param(lambda: True, id="zero"),
        pytest.param(
            lambda _name, _field, _value: True,
            id="three",
        ),
        pytest.param(lambda *_args: True, id="variadic"),
        pytest.param(lambda *, name: bool(name), id="keyword-only"),
    ],
)
def test_model_factory_rejects_invalid_selector_signatures(selector: Any) -> None:
    """Selectors must declare exactly one or two positional parameters."""

    class Config(BaseConfig):
        child: Child

    with pytest.raises(
        TypeError,
        match="selector must declare exactly one or two positional parameters",
    ):
        Config(child=Child(1)).model_factory(selector)


def test_model_factory_propagates_selector_errors() -> None:
    """Selector failures retain their original exception."""

    class Config(BaseConfig):
        child: Child

    def select(_field_name: str) -> bool:
        raise RuntimeError("selection failed")

    with pytest.raises(RuntimeError, match="selection failed"):
        Config(child=Child(1)).model_factory(select)


def test_model_factory_requires_constructible_generated_config() -> None:
    """Missing captured constructor values fail during factorization."""

    class OpaqueTarget:
        def __init__(self, value: int) -> None:
            self.hidden = value

    class Config(BaseConfig):
        target: OpaqueTarget

    with pytest.raises(ValidationError, match="value"):
        Config(target=OpaqueTarget(1)).model_factory()


def test_model_factory_leaves_existing_factories_unchanged() -> None:
    """Already-factorized and unselected models return their existing type."""

    class Config(BaseConfig):
        child: ChildConfig

    source = Config(child=ChildConfig(value=1))

    assert source.model_factory() is Config
    assert source.model_factory(lambda _name: False) is Config


def test_model_factory_preserves_aliases_and_validates_instances() -> None:
    """Generated subclasses retain field metadata and model validation."""
    validator_calls = 0

    class Config(BaseConfig):
        product: Any = Field(alias="PRODUCT", description="Configured product.")

        @field_validator("product")
        @classmethod
        def count_validation(cls, value: Any) -> Any:
            nonlocal validator_calls
            validator_calls += 1
            return value

    source = Config(PRODUCT=Product(3))
    calls_after_construction = validator_calls
    factory_type = source.model_factory()

    assert validator_calls == calls_after_construction
    field = factory_type.model_fields["product"]
    assert field.alias == "PRODUCT"
    assert field.description == "Configured product."
    assert isinstance(field.default, FactoryConfig)
    factory = factory_type()
    assert validator_calls == calls_after_construction + 1
    assert isinstance(factory.product, FactoryConfig)


def test_model_factory_resets_model_config_to_base_defaults() -> None:
    """Generated subclasses own a copy of the base configuration defaults."""

    class Config(
        BaseConfig,
        cli_parse_args=True,
        cli_prefix="types",
        frozen=False,
    ):
        product: Product

    factory_type = Config(product=Product(1)).model_factory()

    assert factory_type.model_config == BaseConfig.model_config
    assert factory_type.model_config is not BaseConfig.model_config
    assert factory_type.model_config.get("cli_parse_args") is None
    assert factory_type.model_config.get("cli_prefix") == ""
    assert factory_type.model_config["frozen"] is True


def test_model_factory_does_not_construct_generated_model() -> None:
    """Generating a model type does not trigger its settings sources."""

    class Config(BaseConfig, cli_parse_args=True):
        product: Product = Field(default_factory=lambda: Product(1))

    source = Config()

    factory_type = source.model_factory()

    default = factory_type.model_fields["product"].default
    assert isinstance(default, FactoryConfig)
    assert default.count == 1


def test_materialize_validates_values_and_calls_target() -> None:
    """Materialization passes validated fields to the target constructor."""
    config_type = cast(Any, FactoryConfig.model_from(Product))
    config = config_type(count="3", label="configured", enabled=False)

    product = config.materialize()

    assert isinstance(product, Product)
    assert product.count == 3
    assert product.label == "configured"
    assert product.enabled is False
    assert config() is not product
    assert FactoryConfig.__call__ is FactoryConfig.materialize
    assert not hasattr(FactoryConfig, "build")


def test_materialize_resolves_nested_factory_configs() -> None:
    """Nested factory configs in fields and containers resolve recursively."""

    class ConfiguredParent:
        def __init__(self, child: Any, children: list[Any]) -> None:
            self.child = child
            self.children = children

    ConfiguredParent.__init__.__annotations__ = {
        "child": ChildConfig,
        "children": list[ChildConfig],
        "return": None,
    }
    parent_config = cast(Any, FactoryConfig.model_from(ConfiguredParent))
    config = parent_config(
        child=ChildConfig(value=1),
        children=[ChildConfig(value=2), ChildConfig(value=3)],
    )

    parent = config.materialize()

    assert isinstance(parent.child, Child)
    assert parent.child.value == 1
    assert [child.value for child in parent.children] == [2, 3]


def test_materialize_propagates_target_errors() -> None:
    """Errors raised by a target constructor are not hidden."""

    class FailingTarget:
        def __init__(self, value: int) -> None:
            raise RuntimeError(value)

    config_type = cast(Any, FactoryConfig.model_from(FailingTarget))

    with pytest.raises(RuntimeError, match="5"):
        config_type(value=5).materialize()


def test_materialize_disables_cli_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target construction cannot consume process CLI arguments."""

    class CliConfig(BaseConfig, cli_parse_args=True):
        value: int = 1

    class Target:
        def __init__(self) -> None:
            self.config = CliConfig()

    config_type = cast(Any, FactoryConfig.model_from(Target))
    monkeypatch.setattr(sys, "argv", ["factory.py", "--value=17"])

    target = config_type().materialize()

    assert target.config.value == 1
    assert CliConfig().value == 17


def test_model_resolve_disables_cli_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved model construction does not reparse process arguments."""

    class Config(BaseConfig, cli_parse_args=True):
        child: ChildConfig = Field(default_factory=lambda: ChildConfig(value=1))

    monkeypatch.setattr(sys, "argv", ["factory.py", "--child.value=17"])
    source = Config()

    resolved = source.model_resolve()

    assert source.child.value == 17
    assert resolved.child.value == 17


def test_model_resolve_uses_instance_values() -> None:
    """Resolution uses the source instance's current validated values."""
    source = ResolvableConfig(PRIMARY=ChildConfig(value=10), label="custom")
    resolved = source.model_resolve()

    assert type(resolved).__name__ == "ResolvableConfigResolved"
    assert issubclass(type(resolved), ResolvableConfig)
    assert isinstance(resolved.primary, Child)
    assert resolved.primary.value == 10
    assert isinstance(source.primary, ChildConfig)
    assert source.primary.value == 10
    assert resolved.model_config["frozen"] is True
    assert resolved.primary_value() == 10
    assert source.label == "custom!"
    assert resolved.label == "custom!!"


def test_model_resolve_preserves_field_metadata_and_resolved_defaults() -> None:
    """Overridden resolved fields retain metadata and remain constructible."""
    resolved = ResolvableConfig().model_resolve()
    resolved_type = type(resolved)
    primary_field = resolved_type.model_fields["primary"]

    assert primary_field.annotation is Child
    assert primary_field.alias == "PRIMARY"
    assert primary_field.description == "Primary child factory."
    assert resolved_type.model_fields["annotated"].description == "Annotated child."

    another = resolved_type()

    assert isinstance(another.primary, Child)
    assert another.primary.value == 1
    assert another.primary is not resolved.primary


def test_resolved_model_preserves_validated_data_default_factory() -> None:
    """Resolved defaults can depend on preceding validated field values."""

    class DependentConfig(BaseConfig):
        seed: int = 3
        child: ChildConfig = Field(
            default_factory=lambda data: ChildConfig(value=data["seed"])
        )

    resolved_type = type(DependentConfig().model_resolve())
    resolved = resolved_type(seed=7)

    assert isinstance(resolved.child, Child)
    assert resolved.child.value == 7


def test_model_resolve_materializes_pydantic_extra_values() -> None:
    """Factory configs stored as Pydantic extras resolve recursively."""

    class OpenModel(BaseModel):
        model_config = ConfigDict(extra="allow")

    class ExtraConfig(BaseConfig):
        nested: OpenModel

    nested = OpenModel.model_validate(
        {"factory": ChildConfig(value=12)},
    )
    source = ExtraConfig(nested=nested)
    resolved = source.model_resolve()
    nested = cast(Any, resolved.nested)

    assert type(nested).__name__ == "OpenModelResolved"
    assert isinstance(nested.factory, Child)
    assert nested.factory.value == 12


def test_model_resolve_preserves_nested_annotation_metadata() -> None:
    """Nested metadata survives factory substitution and unchanged fields."""

    class AnnotationConfig(BaseConfig):
        children: list[Annotated[ChildConfig, Field(description="Nested child.")]]
        positive: list[Annotated[int, Field(gt=0)]] = Field(default_factory=lambda: [1])

    source = AnnotationConfig(children=[ChildConfig(value=13)])
    resolved = source.model_resolve()
    resolved_values = cast(Any, resolved)
    fields = type(resolved).model_fields

    assert isinstance(resolved_values.children[0], Child)
    nested_annotation = get_args(fields["children"].annotation)[0]
    nested_type, nested_metadata = get_args(nested_annotation)
    assert nested_type is Child
    assert nested_metadata.description == "Nested child."
    assert (
        fields["positive"].annotation
        == AnnotationConfig.model_fields["positive"].annotation
    )


def test_model_resolve_handles_recursive_model_annotations() -> None:
    """Recursive schemas resolve factory fields at every concrete level."""

    class RecursiveModel(BaseModel):
        child: ChildConfig
        nested: "RecursiveModel | None" = None

    class RecursiveConfig(BaseConfig):
        recursive: RecursiveModel

    source = RecursiveConfig(
        recursive=RecursiveModel(
            child=ChildConfig(value=15),
            nested=RecursiveModel(child=ChildConfig(value=16)),
        )
    )
    resolved = source.model_resolve()
    recursive = cast(Any, resolved.recursive)

    assert type(recursive).__name__ == "RecursiveModelResolved"
    assert isinstance(recursive.child, Child)
    assert type(recursive.nested).__name__ == "RecursiveModelResolved"
    assert isinstance(recursive.nested.child, Child)


def test_model_resolve_transforms_nested_models_and_containers() -> None:
    """Declared concrete factories resolve throughout supported annotations."""
    source = ResolvableConfig(
        optional=ChildConfig(value=4),
        choice=ChildConfig(value=5),
        mapping={"child": ChildConfig(value=6)},
        sequence=[ChildConfig(value=7)],
        fixed=(ChildConfig(value=8),),
        nested=NestedModel(child=ChildConfig(value=11)),
    )
    source = source.model_copy(
        update={
            "keyed": {ChildConfig(value=8): "child"},
            "unique": {ChildConfig(value=9)},
            "frozen_unique": frozenset({ChildConfig(value=10)}),
        }
    )

    resolved = source.model_resolve()
    resolved_values = cast(Any, resolved)

    assert isinstance(resolved_values.optional, Child)
    assert isinstance(resolved_values.choice, Child)
    assert isinstance(resolved_values.annotated, Child)
    assert isinstance(resolved_values.mapping["child"], Child)
    assert all(isinstance(child, Child) for child in resolved_values.keyed)
    assert isinstance(resolved_values.sequence[0], Child)
    assert isinstance(resolved_values.fixed[0], Child)
    assert all(isinstance(child, Child) for child in resolved_values.unique)
    assert all(isinstance(child, Child) for child in resolved_values.frozen_unique)
    assert type(resolved_values.nested).__name__ == "NestedModelResolved"
    assert isinstance(resolved_values.nested, NestedModel)
    assert isinstance(resolved_values.nested.child, Child)

    fields = type(resolved).model_fields
    assert fields["optional"].annotation == Child | None
    assert fields["choice"].annotation == Child | str
    assert fields["mapping"].annotation == dict[str, Child]
    assert fields["keyed"].annotation == dict[Child, str]
    assert fields["sequence"].annotation == list[Child]
    assert fields["fixed"].annotation == tuple[Child, ...]
    assert fields["unique"].annotation == set[Child]
    assert fields["frozen_unique"].annotation == frozenset[Child]


def test_model_resolve_rejects_bare_factory_annotation() -> None:
    """A bare FactoryConfig does not identify a stable target annotation."""

    class BareConfig(BaseConfig):
        factory: FactoryConfig

    source = BareConfig(factory=ChildConfig(value=1))

    with pytest.raises(
        TypeError,
        match="FactoryConfig annotations must use a concrete generated subclass",
    ):
        source.model_resolve()


def test_model_resolve_requires_an_instance() -> None:
    """The normal method cannot be called without a config instance."""
    with pytest.raises(TypeError, match="missing 1 required positional argument"):
        cast(Any, ResolvableConfig).model_resolve()


def test_model_resolve_rejects_cyclic_values() -> None:
    """Recursive resolution reports active object cycles clearly."""

    class CyclicConfig(BaseConfig):
        value: Any

    cycle: list[Any] = []
    cycle.append(cycle)
    source = CyclicConfig.model_construct(value=cycle)

    with pytest.raises(ValueError, match="cyclic values cannot be resolved"):
        source.model_resolve()
