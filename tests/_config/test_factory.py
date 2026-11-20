"""Factory validation, target compatibility, and public construction methods."""

from typing import Any

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    create_model,
    field_serializer,
)
from pydantic_core import PydanticSerializationError

from confidantic import BaseConfig, Factory
from tests._config.factory_targets import (
    Child,
    DerivedTarget,
    Product,
    ProductModel,
    SimpleTarget,
    UnrelatedTarget,
)


def test_model_from_type_returns_typed_factory() -> None:
    """Target types produce instances accepted by typed factory fields."""

    factory = ProductModel(factory=Factory.model_from(Product)).factory

    assert factory.factory_target is Product


def test_generic_factory_accepts_target_classes_and_instances() -> None:
    """Generic factories convert compatible target classes and instances."""

    class Model(BaseModel):
        factory: Factory[Product]

    source = Product(3, "source", enabled=False)

    assert Model(factory=Product).factory.factory_target is Product
    product = Model(factory=source).factory.instance()
    assert (product.count, product.label, product.enabled) == (3, "source", False)


def test_model_from_instance_returns_typed_factory() -> None:
    """Target instances produce typed factories with derived defaults."""
    source = Product(3, "source", enabled=False)

    factory = ProductModel(factory=Factory.model_from(source)()).factory

    assert factory.factory_target is Product
    product = factory.instance()
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
    product = factory.instance()
    assert (product.count, product.label, product.enabled) == (4, "source", False)


def test_typed_factory_field_preserves_factory_type() -> None:
    """Typed factory fields preserve an already-generated factory class."""
    factory_type = Factory.model_from(Product)

    assert (
        ProductModel.model_validate({"factory": factory_type}).factory is factory_type
    )


def test_typed_factory_field_preserves_factory_instances() -> None:
    """Typed factory fields preserve already-generated factory instances."""
    factory_type = Factory.model_from(Product)

    factory = ProductModel.model_validate({"factory": factory_type(count=1)}).factory

    assert factory.factory_target is Product


def test_generic_factory_validation_rejects_incompatible_factory() -> None:
    """Generic factory fields reject factories targeting another type."""

    class Model(BaseModel):
        child: Factory[Child]

    other_type = Factory.model_from(Product)

    with pytest.raises(ValidationError, match="expected target type"):
        Model.model_validate({"child": other_type(count=1)})


def test_generic_factory_validation_rejects_incompatible_target_instance() -> None:
    """Generic factory fields reject incompatible target instances."""

    class Model(BaseModel):
        child: Factory[Child]

    with pytest.raises(ValidationError, match="target instance"):
        Model.model_validate({"child": Product(1)})


def test_generic_factory_validation_converts_target_instance() -> None:
    """Generic factory fields convert compatible target instances."""

    class Model(BaseModel):
        child: Factory[Child]

    model = Model.model_validate({"child": Child(value=4)})

    assert model.child.instance().value == 4


def test_specialized_factory_rejects_wrong_model_from_target() -> None:
    """Specialized factories enforce their target type when generating models."""
    with pytest.raises(TypeError, match="expects Child"):
        Factory[Child].model_from(Product)


def test_factory_field_composes_with_containers_and_unions() -> None:
    """Generic factory validation composes with standard Pydantic annotations."""

    class Model(BaseModel):
        factories: list[Factory[Child]]
        optional: Factory[Child] | None
        choice: Factory[Child] | str

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

        factory: Factory[Product] | PositionalTarget

    assert isinstance(Model(factory=PositionalTarget(12)).factory, PositionalTarget)


def test_instance_from_accepts_custom_name() -> None:
    """Instance factories use the double-underscore model name keyword."""
    factory = Factory.instance_from(Product, __name__="ConfiguredProduct", count=1)

    assert type(factory).__name__ == "ConfiguredProduct"


def test_instance_uses_validated_values_and_calls_target() -> None:
    """Resolution passes validated fields to the target constructor."""
    config = Factory.model_from(Product)(count="3", label="configured", enabled=False)

    product = config.instance()

    assert isinstance(product, Product)
    assert product.count == 3
    assert product.label == "configured"
    assert product.enabled is False
    assert config.instance() is not product
    assert not hasattr(config, "materialize")
    assert not callable(config)


def test_instance_uses_values_copied_before_construction() -> None:
    """Updated values are copied before recursive resolution."""
    config = Factory.model_from(Product)(count=3, label="configured", enabled=False)

    product = config.copy(label="overridden", enabled=True).instance()

    assert product.label == "overridden"
    assert product.enabled is True


def test_factory_model_resolve_does_not_accept_updates() -> None:
    """Factory resolution operates only on its validated configuration."""
    config = Factory.model_from(Product)(count=1)

    with pytest.raises(TypeError):
        config.model_resolve({"count": "2"})


def test_factory_instance_accepts_validated_copies() -> None:
    """Copied values are validated before recursive resolution."""
    config = Factory.model_from(Product)(count=1)

    product = config.copy(count="2").instance()

    assert product.count == 2


def test_factory_default_target_class_is_converted() -> None:
    """A generated factory class can be used as a typed default."""
    config_type = create_model(
        "Config",
        __base__=BaseConfig,
        service=(Factory[Child], Factory.model_from(Child)),
    )

    assert config_type().service.factory_target is Child


def test_factory_default_factory_class_is_preserved() -> None:
    """A concrete factory class default is preserved without regeneration."""

    factory_type = Factory.model_from(Child)

    class Config(BaseConfig):
        service: Factory[Child] = factory_type

    service = Config().service

    assert service is factory_type


def test_factory_instance_default_is_preserved() -> None:
    """Factory instances are preserved by generic Factory fields."""

    class Config(BaseConfig):
        service: Factory[Child] = Factory.instance_from(Child)  # type: ignore[assignment]

    assert Config().service.instance() is not None


def test_factory_field_accepts_a_factory_for_a_target_subclass() -> None:
    """Typed factory fields accept factories for compatible target subclasses."""

    class Parent:
        pass

    class ChildTarget(Parent):
        def __init__(self, value: int = 1) -> None:
            self.value = value

    class Config(BaseModel):
        service: Factory[Parent]

    factory_type = Factory.model_from(ChildTarget(value=2))
    config = Config(service=factory_type)

    assert config.service is factory_type
    assert isinstance(config.service().instance().value, int)
    assert config.service().instance().value == 2


def test_factory_field_rejects_a_factory_for_another_target() -> None:
    """Typed factory fields reject concrete factories for another target."""

    class Other:
        def __init__(self, name: str = "other") -> None:
            self.name = name

    class Config(BaseModel):
        service: Factory[Child]

    other = Factory.model_from(Other)

    with pytest.raises(ValidationError):
        Config(service=other)


def test_factory_field_rejects_a_target_class_for_another_target() -> None:
    """Typed factory fields reject target classes of another type."""

    class Other:
        def __init__(self, name: str = "other") -> None:
            self.name = name

    class Config(BaseModel):
        service: Factory[Child]

    with pytest.raises(ValidationError):
        Config(service=Other)


def test_factory_default_factory_is_converted() -> None:
    """Normal Pydantic default factories remain supported."""

    class Config(BaseConfig):
        service: Factory[Child] = Field(
            default_factory=lambda: Factory.model_from(Child)
        )

    assert Config().service.factory_target is Child


def test_invalid_factory_input_reports_validation_error() -> None:
    """Factory validation exposes an ordinary Pydantic validation error."""
    with pytest.raises(ValidationError, match="Factory"):
        ProductModel.model_validate({"factory": object()})


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_factory_target_compatibility(strict: bool, nested: bool) -> None:
    class Config(BaseModel):
        target: Factory[SimpleTarget]

    adapter = TypeAdapter(Config if nested else Factory[SimpleTarget])
    wrong = Factory.instance_from(UnrelatedTarget)
    with pytest.raises(ValidationError, match="expected target"):
        adapter.validate_python({"target": wrong} if nested else wrong, strict=strict)
    for target in (SimpleTarget, DerivedTarget):
        original = Factory.instance_from(target)
        result = adapter.validate_python(
            {"target": original} if nested else original, strict=strict
        )
        assert (result.target if nested else result) is original


@pytest.mark.parametrize(
    "value", [SimpleTarget, SimpleTarget(), Factory.model_from(SimpleTarget)]
)
def test_factory_strict_input_shapes(value: Any) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Factory[SimpleTarget]).validate_python(value, strict=True)


@pytest.mark.parametrize("dump", ["model_dump", "model_dump_json"])
def test_factory_serializer_error_propagates(dump: str) -> None:
    class Broken(Factory.model_from(SimpleTarget)):
        @field_serializer("value")
        def broken(self, value: int) -> int:
            raise ValueError("deliberate serializer failure")

    with pytest.raises(
        PydanticSerializationError, match="deliberate serializer failure"
    ):
        getattr(Broken(), dump)()


def test_instance_merges_runtime_arguments_without_validation_or_mutation() -> None:
    """Runtime arguments override settings while copied updates remain validated."""
    config = Factory.instance_from(Product, count=1, label="configured")
    result = config.instance(
        "raw", "runtime", object(), "extra", enabled=False, other=7
    )
    assert result.count == "raw"
    assert result.label == "runtime"
    assert result.args == ("extra",)
    assert result.enabled is False
    assert result.kwargs == {"other": 7}
    assert config.count == 1
    assert config.label == "configured"
    assert config.copy(count="2").instance().count == 2
    assert config.instance(count="2").count == "2"


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        ((), {}, "missing a required argument.*count"),
        ((1,), {"count": 2}, "multiple values"),
    ],
    ids=["missing", "duplicate"],
)
def test_partial_factory_reports_invalid_runtime_bindings(
    args: tuple[Any, ...], kwargs: dict[str, Any], message: str
) -> None:
    """Partial configs are valid before their remaining inputs are supplied."""
    config = Factory.instance_from(Product, __exclude__={"count"})
    with pytest.raises(TypeError, match=message):
        config.instance(*args, **kwargs)
    assert config.instance(count=2).count == 2


def test_runtime_bindings_support_positional_only_and_keyword_only_inputs() -> None:
    """Excluded positional inputs keep their original constructor positions."""

    class Target:
        def __init__(self, token: Any, /, count: int = 1, *, required: str) -> None:
            self.token = token
            self.count = count
            self.required = required

    config = Factory.instance_from(Target, __exclude__={"token", "required"})
    token = object()
    result = config.instance(token, "raw", required="runtime")
    assert (result.token, result.count, result.required) == (token, "raw", "runtime")
    for args, kwargs in [
        ((token,), {}),
        ((token,), {"unexpected": True}),
        ((), {"token": token, "required": "x"}),
    ]:
        with pytest.raises(TypeError):
            config.instance(*args, **kwargs)


def test_runtime_defaults_and_variadic_arguments_keep_constructor_semantics() -> None:
    """Excluded defaults remain available without entering recursive traversal."""
    default = Factory.instance_from(SimpleTarget)

    class Target:
        def __init__(
            self,
            prefix: Any = default,
            /,
            count: int = 2,
            *items: Any,
            flag: bool = True,
            **extras: Any,
        ) -> None:
            self.values = (prefix, count, items, flag, extras)

    config = Factory.instance_from(Target, __exclude__={"prefix"})
    result = config.instance(flag=False, self="allowed")
    assert result.values == (default, 2, (), False, {"self": "allowed"})
    assert result.values[0] is default
    nested = Factory.instance_from(SimpleTarget, value=8)
    result = config.instance("runtime", 4, nested, extra=nested)
    assert result.values[:2] == ("runtime", 4)
    assert result.values[2][0].value == result.values[4]["extra"].value == 8
    assert result.values[2][0] is not result.values[4]["extra"]


def test_instance_uses_excluded_constructor_defaults_instead_of_template_values() -> (
    None
):
    """Selecting a template subset does not retain hidden constructor inputs."""
    template = Product(7, label="template")
    config = Factory.instance_from(template, __include__={"count"})
    assert config.instance().label == "default"
    assert config.instance().count == 7


def test_root_factory_resolution_preserves_model_and_construction_method() -> None:
    """Both model types share root-preserving resolution semantics."""
    config = Factory.instance_from(Product, count=2)
    resolved = config.model_resolve(name="PreparedProduct")
    assert Factory.model_resolve is BaseConfig.model_resolve
    assert isinstance(resolved, Factory)
    assert resolved is not config
    assert type(resolved).__name__ == "PreparedProduct"
    assert resolved.factory_target is Product
    assert resolved.instance().count == 2
    assert not callable(resolved)


def test_partial_factory_dump_and_make_directive() -> None:
    """Ordinary dumps restore the schema; Make directives still require inputs."""
    from confidantic.utils import make

    config = Factory.instance_from(Product, __exclude__={"count"}, label="saved")
    restored = type(config).model_validate_json(config.model_dump_json())
    assert restored.instance(4).label == "saved"
    directive = config.model_dump(context={"make": True})
    assert "count" not in directive
    with pytest.raises(TypeError):
        make(directive)
    assert make({**directive, "count": 4}).label == "saved"


def test_constructor_receiver_name_does_not_reserve_runtime_keywords() -> None:
    """The receiver is removed by position; self remains a valid target input."""

    class Target:
        def __init__(receiver, self: str, value: int = 1) -> None:
            receiver.input = self
            receiver.value = value

    config = Factory.instance_from(Target, __exclude__={"self"})
    assert config.instance(self="runtime").input == "runtime"
    assert config.instance("positional").input == "positional"


def test_positional_only_default_can_share_name_with_extra_keyword() -> None:
    """A positional-only parameter does not consume a same-named extra keyword."""

    class Target:
        def __init__(self, value: int = 1, /, **extras: Any) -> None:
            self.value = value
            self.extras = extras

    config = Factory.instance_from(Target, __include__=set())
    result = config.instance(value=7)
    assert result.value == 1
    assert result.extras == {"value": 7}
    result = config.instance(2, value=7)
    assert result.value == 2
    assert result.extras == {"value": 7}


def test_instance_does_not_reload_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime construction uses stored values even if settings have changed."""
    config = Factory.model_from(Product)(count=1, _env_prefix="RUNTIME_")
    monkeypatch.setenv("RUNTIME_COUNT", "99")
    assert config.instance().count == 1
    assert config.instance(count="raw").count == "raw"
