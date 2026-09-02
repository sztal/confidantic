"""Configuration models generated from object constructors."""

import sys
from collections.abc import (
    Callable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
)
from copy import deepcopy
from inspect import Parameter, signature
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Generic,
    Self,
    TypeVar,
    cast,
    get_type_hints,
)

from pydantic import Field as PydanticField
from pydantic import GetCoreSchemaHandler, create_model
from pydantic.functional_validators import WrapValidator
from pydantic_core import (
    CoreSchema,
    PydanticCustomError,
    PydanticUndefined,
    core_schema,
)

from confidantic._config.base import (
    _DISABLE_CLI_PARSE_ARGS,
    BaseConfig,
)

__all__ = ("Factory",)

T = TypeVar("T")
U = TypeVar("U")


def _factory_target(factory_type: type[Any]) -> type[Any] | None:
    target = cast(type[Any] | None, getattr(factory_type, "factory_target", None))
    if target is not None:
        return target
    arguments = getattr(factory_type, "__pydantic_generic_metadata__", {}).get(
        "args", ()
    )
    if len(arguments) == 1 and isinstance(arguments[0], type):
        return arguments[0]
    return None


class Factory(BaseConfig, Generic[T]):
    """Configuration generated from a target type's constructor.

    Concrete subclasses are created with :meth:`model_from`. Their fields
    correspond to annotated constructor parameters and validated instances can
    create the target object by calling :meth:`materialize` or the config itself.

    Pydantic fields accept target instances and convert them to generated
    factory config instances. Mappings supplied to concrete factory config
    fields retain normal Pydantic model validation.
    """

    factory_target: ClassVar[type[T]]
    factory_fields: ClassVar[tuple[str, ...]] = ()

    if TYPE_CHECKING:
        Field: ClassVar[Any]
    else:

        class Field(Generic[U]):
            """A typed field that stores a factory configuration class."""

            @classmethod
            def __class_getitem__(cls, item_type: type[U]) -> Any:
                """Return a factory-class annotation for ``item_type``."""
                if not isinstance(item_type, type):
                    raise TypeError("Factory.Field requires a target type")

                def validate(value: Any, handler: Callable[[Any], Any]) -> Any:
                    if isinstance(value, type) and issubclass(value, Factory):
                        if value.factory_target is not item_type:
                            raise PydanticCustomError(
                                "factory",
                                "Input should be a Factory for the expected target type",
                            )
                        return value
                    if isinstance(value, type) and value is item_type:
                        return Factory.model_from(value)
                    if isinstance(value, item_type):
                        return Factory.model_from(value)
                    raise PydanticCustomError(
                        "factory",
                        "Input should be a target type or Factory type",
                    )

                return Annotated[type[Factory[U]], WrapValidator(validate)]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        target = _factory_target(cls) or _factory_target(source_type)
        generic_arguments = getattr(cls, "__pydantic_generic_metadata__", {}).get(
            "args", ()
        )
        schema = handler(
            cls.model_from(target)
            if target is not None and generic_arguments
            else source_type
        )

        def validate(value: Any, next_validator: Callable[[Any], Any]) -> Any:
            if isinstance(value, Factory):
                if target is not None and value.factory_target is not target:
                    raise PydanticCustomError(
                        "factory",
                        "Input should be a Factory for the expected target type",
                    )
                return value
            if isinstance(value, Mapping):
                return next_validator(value)
            try:
                value_target = value if isinstance(value, type) else type(value)
                if target is not None and value_target is not target:
                    raise TypeError
                config: Factory[Any] = Factory.model_from(value)()
                return next_validator(config.model_dump())
            except (TypeError, ValueError) as error:
                raise PydanticCustomError(
                    "factory",
                    "Input should be a Factory, target instance, or mapping",
                ) from error

        lax_schema = core_schema.no_info_wrap_validator_function(validate, schema)
        factory_base = next(
            base for base in cls.__mro__ if BaseConfig in base.__bases__
        )
        strict_schema = core_schema.union_schema(
            [schema, core_schema.is_instance_schema(factory_base)],
            mode="left_to_right",
        )
        return core_schema.lax_or_strict_schema(lax_schema, strict_schema)

    @classmethod
    def model_from(
        cls,
        source: type[Any] | Any,
        *,
        name: str | None = None,
    ) -> type[Self]:
        """Create a concrete factory config from a target type or instance.

        Constructor annotations define the generated fields. When ``source``
        is an instance, its available values replace constructor defaults;
        mutable and unhashable values are copied through field default
        factories.

        Parameters
        ----------
        source
            Target type, or an instance whose type and current attribute values
            define the generated configuration model.
        name
                Optional generated model name. By default, append ``Config`` to
                the target type name.

        Returns
        -------
        type[Factory]
            Generated concrete configuration class.
        """
        target = source if isinstance(source, type) else type(source)
        expected_target = _factory_target(cls)
        if expected_target is not None and target is not expected_target:
            msg = f"{cls.__name__} expects {expected_target.__name__}"
            raise TypeError(msg)
        instance = None if isinstance(source, type) else source
        return cls._model_from(instance, target, name=name)

    @classmethod
    def instance_from(
        cls, source: type[Any] | Any, *, name: str | None = None, **kwargs: Any
    ) -> Self:
        """Create a new factory config instance from a source.

        Parameters
        ----------
        name
            Optional generated model name.
        **kwargs
            Values for the generated fields. Unspecified fields use their
            default values.

        Returns
        -------
        Self
            New factory config instance.
        """
        return cls.model_from(source, name=name)(**kwargs)

    def materialize(self, **kwargs: Any) -> Any:
        """Create the target object from the validated configuration values.

        CLI parsing is disabled throughout materialization, including any
        configuration models constructed by the target.

        Returns
        -------
        T
            Instance of the target type recorded by :meth:`model_from`.
        """
        token = _DISABLE_CLI_PARSE_ARGS.set(True)
        try:
            return _materialize_factory(self, set(), **kwargs)
        finally:
            _DISABLE_CLI_PARSE_ARGS.reset(token)

    __call__ = materialize

    @classmethod
    def _model_from(
        cls,
        instance: object | None,
        target: type[T],
        *,
        name: str | None,
    ) -> type[Self]:
        init = target.__init__
        namespace: dict[str, Any] = {}
        for base in reversed(target.__mro__):
            module = sys.modules.get(base.__module__)
            if module is not None:
                namespace.update(vars(module))
        namespace.update(getattr(init, "__globals__", {}))
        annotations = get_type_hints(
            init,
            globalns=namespace,
            localns=namespace,
            include_extras=True,
        )
        fields: dict[str, tuple[Any, Any]] = {}

        for index, (field_name, parameter) in enumerate(
            signature(init).parameters.items()
        ):
            if index == 0 and field_name in {"self", "cls"}:
                continue
            if field_name not in annotations:
                continue
            if parameter.kind is Parameter.POSITIONAL_ONLY:
                msg = (
                    f"{target.__qualname__}.__init__ parameter {field_name!r} "
                    "is positional-only"
                )
                raise TypeError(msg)
            if parameter.kind in {
                Parameter.VAR_POSITIONAL,
                Parameter.VAR_KEYWORD,
            }:
                continue

            default = parameter.default
            if instance is not None and hasattr(instance, field_name):
                default = getattr(instance, field_name)
                if _requires_default_factory(default):
                    default = PydanticField(default_factory=_cloned_default(default))
            elif default is Parameter.empty:
                default = PydanticUndefined
            fields[field_name] = (annotations[field_name], default)

        model = create_model(
            name or f"{target.__name__}Config",
            __base__=cls,
            __module__=target.__module__,
            **cast(dict[str, Any], fields),
        )
        model.factory_target = target
        model.factory_fields = tuple(fields)
        return model


def _cloned_default(value: Any) -> Callable[[], Any]:
    def default_factory() -> Any:
        return deepcopy(value)

    return default_factory


def _requires_default_factory(value: Any) -> bool:
    if isinstance(
        value,
        MutableMapping | MutableSequence | MutableSet | bytearray,
    ):
        return True
    try:
        hash(value)
    except TypeError:
        return True
    return False


def _enter_resolution(value: Any, active: set[int]) -> int:
    identity = id(value)
    if identity in active:
        msg = "cyclic values cannot be resolved"
        raise ValueError(msg)
    active.add(identity)
    return identity


def _materialize_factory(config: Factory[Any], active: set[int], **kwargs: Any) -> Any:
    identity = _enter_resolution(config, active)
    try:
        values = {
            field_name: _resolve_value(getattr(config, field_name), active)
            for field_name in config.factory_fields
        }
        if kwargs:
            values.update(kwargs)
        return config.factory_target(**values)
    finally:
        active.remove(identity)


def _resolve_value(value: Any, active: set[int]) -> Any:
    if isinstance(value, Factory):
        return _materialize_factory(value, active)
    if isinstance(value, Mapping):
        identity = _enter_resolution(value, active)
        try:
            return {
                _resolve_value(key, active): _resolve_value(item, active)
                for key, item in value.items()
            }
        finally:
            active.remove(identity)
    if isinstance(value, list):
        identity = _enter_resolution(value, active)
        try:
            return [_resolve_value(item, active) for item in value]
        finally:
            active.remove(identity)
    if isinstance(value, tuple):
        identity = _enter_resolution(value, active)
        try:
            return tuple(_resolve_value(item, active) for item in value)
        finally:
            active.remove(identity)
    if isinstance(value, set):
        identity = _enter_resolution(value, active)
        try:
            return {_resolve_value(item, active) for item in value}
        finally:
            active.remove(identity)
    if isinstance(value, frozenset):
        identity = _enter_resolution(value, active)
        try:
            return frozenset(_resolve_value(item, active) for item in value)
        finally:
            active.remove(identity)
    return value
