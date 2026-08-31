"""Tests for constructor-derived factory configuration models."""

import sys
from typing import Annotated, Any, cast, get_args

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from confidantic import BaseConfig, FactoryConfig
from confidantic import ConfigModelDict as ConfigModelDict
from confidantic.annotations import Make

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

    model_config = ConfigModelDict(frozen=True)

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


def test_factory_field_deserializes_make_directive() -> None:
    """Make directive data resolves to its concrete configuration type."""

    class Model(BaseModel):
        factory: Make[FactoryConfig]

    source = ChildConfig(value=6)
    model = Model.model_validate({"factory": source.model_dump(context={"make": True})})

    assert type(model.factory) is ChildConfig
    assert model.factory == source


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
    """Only annotated keyword-capable constructor parameters become fields."""
    config_type = cast(Any, FactoryConfig.model_from(Product))

    assert config_type.__name__ == "ProductConfig"
    assert issubclass(config_type, FactoryConfig)
    assert config_type.factory_target is Product
    assert config_type.factory_fields == ("count", "label", "enabled")
    assert tuple(config_type.model_fields) == ("count", "label", "enabled")
    assert config_type.model_fields["count"].is_required()
    assert config_type.model_fields["label"].default == "default"
    assert config_type.model_fields["enabled"].default is True


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
    assert resolved.model_config["frozen"] is True  # type: ignore[truthy-function]
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
            "keyed": {ChildConfig(value=8): "child"},  # type: ignore[dict-item]
            "unique": {ChildConfig(value=9)},  # type: ignore[dict-item]
            "frozen_unique": frozenset({ChildConfig(value=10)}),  # type: ignore[dict-item]
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
