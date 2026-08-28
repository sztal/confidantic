"""Configuration models generated from object constructors."""

from collections.abc import (
    Callable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
)
from copy import copy, deepcopy
from functools import reduce, singledispatchmethod
from inspect import Parameter, signature
from operator import or_
from types import UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Self,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, create_model
from pydantic.fields import FieldInfo
from pydantic_core import (
    CoreSchema,
    PydanticCustomError,
    PydanticUndefined,
    core_schema,
)

from confidantic.config.base import (
    _DISABLE_CLI_PARSE_ARGS,
    BaseConfig,
)

__all__ = ("FactoryConfig",)

_RESOLVED_MODEL_TYPES: dict[type[BaseModel], type[BaseModel]] = {}
_RESOLVING_MODEL_TYPES: set[type[BaseModel]] = set()


class _ArbitraryTypesModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


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


class FactoryConfig(BaseConfig):
    """Configuration generated from a target type's constructor.

    Concrete subclasses are created with :meth:`model_from`. Their fields
    correspond to annotated constructor parameters and validated instances can
    create the target object by calling :meth:`materialize` or the config itself.

    Pydantic fields accept target instances and convert them to generated
    factory config instances. Mappings supplied to concrete factory config
    fields retain normal Pydantic model validation.
    """

    factory_target: ClassVar[type[Any]]
    factory_fields: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        schema = handler(source_type)

        def validate(value: Any, next_validator: Callable[[Any], Any]) -> Any:
            if isinstance(value, FactoryConfig):
                return value
            if getattr(cls, "factory_target", None) is not None and isinstance(
                value, Mapping
            ):
                return next_validator(value)
            try:
                config_type = cls.model_from(value)
                return next_validator(config_type())
            except (TypeError, ValueError) as error:
                raise PydanticCustomError(
                    "factory_config",
                    "Input should be a FactoryConfig, target instance, or mapping",
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

    @singledispatchmethod
    @classmethod
    def model_from(
        cls,
        source: object,
        *,
        name: str | None = None,
    ) -> type[Self]:
        """Create a concrete factory config from a target instance.

        Constructor annotations must match the target signature. Annotated
        keyword parameters define the generated fields. Values available on
        ``source`` replace constructor defaults; mutable and unhashable values
        are copied through field default factories.

        Parameters
        ----------
        source
                Target instance whose type and current attribute values define the
                generated configuration model.
        name
                Optional generated model name. By default, append ``Config`` to
                the target type name.

        Returns
        -------
        type[FactoryConfig]
                Generated concrete configuration class.
        """
        return cls._model_from(source, type(source), name=name)

    @model_from.register(type)
    @classmethod
    def _model_from_type(
        cls,
        source: type[Any],
        *,
        name: str | None = None,
    ) -> type[Self]:
        return cls._model_from(None, source, name=name)

    @classmethod
    def _model_from(
        cls,
        instance: object | None,
        target: type[Any],
        *,
        name: str | None,
    ) -> type[Self]:
        init = target.__init__
        annotations = get_type_hints(init, include_extras=True)
        parameters = tuple(signature(init).parameters.items())
        parameter_names = {
            field_name
            for index, (field_name, _) in enumerate(parameters)
            if index != 0 or field_name not in {"self", "cls"}
        }
        annotation_names = set(annotations) - {"return"}
        if parameter_names != annotation_names:
            missing = ", ".join(sorted(parameter_names - annotation_names))
            unexpected = ", ".join(sorted(annotation_names - parameter_names))
            details = []
            if missing:
                details.append(f"missing annotations for: {missing}")
            if unexpected:
                details.append(f"annotations without parameters: {unexpected}")
            msg = (
                f"{target.__qualname__}.__init__ type annotations do not match "
                f"its signature ({'; '.join(details)}); cannot create a model "
                "factory config"
            )
            raise TypeError(msg)
        fields: dict[str, tuple[Any, Any]] = {}

        for index, (field_name, parameter) in enumerate(parameters):
            if index == 0 and field_name in {"self", "cls"}:
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
                    default = Field(default_factory=_cloned_default(default))
            elif default is Parameter.empty:
                default = PydanticUndefined
            fields[field_name] = (annotations[field_name], default)

        model = create_model(
            name or f"{target.__name__}Config",
            __base__=cls,
            **cast(dict[str, Any], fields),
        )
        model.factory_target = target
        model.factory_fields = tuple(fields)
        return model

    def materialize(self) -> Any:
        """Create the target object from the validated configuration values.

        CLI parsing is disabled throughout materialization, including any
        configuration models constructed by the target.

        Returns
        -------
        Any
                Instance of the target type recorded by :meth:`model_from`.
        """
        token = _DISABLE_CLI_PARSE_ARGS.set(True)
        try:
            return _materialize_factory(self, set())
        finally:
            _DISABLE_CLI_PARSE_ARGS.reset(token)

    __call__ = materialize


def _resolved_annotation(annotation: Any) -> Any:
    if isinstance(annotation, type):
        if issubclass(annotation, FactoryConfig):
            target = getattr(annotation, "factory_target", None)
            if target is None:
                msg = "FactoryConfig annotations must use a concrete generated subclass"
                raise TypeError(msg)
            return target
        if issubclass(annotation, BaseModel):
            return _resolved_model_type(annotation)
        return annotation

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin is Annotated:
        resolved = _resolved_annotation(arguments[0])
        if resolved == arguments[0]:
            return annotation
        return annotation.copy_with((resolved,))
    if origin not in {
        Union,
        UnionType,
        Mapping,
        MutableMapping,
        dict,
        list,
        tuple,
        set,
        frozenset,
    }:
        return annotation

    resolved_arguments = tuple(_resolved_annotation(item) for item in arguments)
    if resolved_arguments == arguments:
        return annotation
    copy_with = getattr(annotation, "copy_with", None)
    if copy_with is not None:
        return copy_with(resolved_arguments)
    if origin is UnionType:
        return reduce(or_, resolved_arguments)
    parameters: Any = (
        resolved_arguments[0] if len(resolved_arguments) == 1 else resolved_arguments
    )
    return origin[parameters]


def _resolved_default_factory(field: FieldInfo) -> Callable[..., Any]:
    original = field.default_factory
    if original is None:
        value = field.default

        def static_default_factory() -> Any:
            return _resolve_value(deepcopy(value), set())

        return static_default_factory

    if field.default_factory_takes_validated_data:
        validated_factory = cast(Callable[[dict[str, Any]], Any], original)

        def validated_default_factory(validated_data: dict[str, Any]) -> Any:
            return _resolve_value(validated_factory(validated_data), set())

        return validated_default_factory

    plain_factory = cast(Callable[[], Any], original)

    def plain_default_factory() -> Any:
        return _resolve_value(plain_factory(), set())

    return plain_default_factory


def _resolved_field(field: FieldInfo, annotation: Any) -> FieldInfo:
    resolved = copy(field)
    resolved.annotation = annotation
    if not field.is_required():
        resolved.default = PydanticUndefined
        resolved.default_factory = _resolved_default_factory(field)
    return resolved


def _model_factory(
    config: BaseConfig,
    selector: Callable[[str], bool] | Callable[[str, FieldInfo], bool] | None = None,
    *,
    clear_metadata: bool = True,
) -> type[BaseConfig]:
    selector_arity = 1
    if selector is not None:
        parameters = tuple(signature(selector).parameters.values())
        if len(parameters) not in {1, 2} or any(
            parameter.kind
            not in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in parameters
        ):
            msg = "selector must declare exactly one or two positional parameters"
            raise TypeError(msg)
        selector_arity = len(parameters)

    source_type = type(config)
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, field in source_type.model_fields.items():
        value = getattr(config, field_name)
        selected = selector is None or (
            selector(field_name) if selector_arity == 1 else selector(field_name, field)
        )
        if not selected or isinstance(value, FactoryConfig):
            continue

        factory_type = FactoryConfig.model_from(value)
        factory_default = factory_type()
        factory_field = copy(field)
        factory_field.annotation = factory_type
        factory_field.default = factory_default
        factory_field.default_factory = None
        if clear_metadata:
            factory_field.metadata = []
        fields[field_name] = (factory_type, factory_field)

    if not fields:
        return source_type

    return cast(
        type[BaseConfig],
        create_model(
            f"{source_type.__name__}Factory",
            __base__=source_type,
            __config__=copy(BaseConfig.model_config),
            __module__=source_type.__module__,
            **cast(dict[str, Any], fields),
        ),
    )


def _resolved_model_type(
    source: type[BaseModel],
    *,
    force: bool = False,
) -> type[BaseModel]:
    cached = _RESOLVED_MODEL_TYPES.get(source)
    if cached is not None:
        return cached
    if source in _RESOLVING_MODEL_TYPES:
        return source

    _RESOLVING_MODEL_TYPES.add(source)
    try:
        fields: dict[str, tuple[Any, Any]] = {}
        for field_name, field in source.model_fields.items():
            annotation = _resolved_annotation(field.annotation)
            if annotation != field.annotation:
                fields[field_name] = (
                    annotation,
                    _resolved_field(field, annotation),
                )

        if not fields and not force:
            return source
        base: type[BaseModel] | tuple[type[BaseModel], ...] = source
        if not source.model_config.get("arbitrary_types_allowed"):
            base = (source, _ArbitraryTypesModel)
        resolved = cast(
            type[BaseModel],
            create_model(
                f"{source.__name__}Resolved",
                __base__=base,
                __module__=source.__module__,
                **cast(dict[str, Any], fields),
            ),
        )
        _RESOLVED_MODEL_TYPES[source] = resolved
        return resolved
    finally:
        _RESOLVING_MODEL_TYPES.remove(source)


def _enter_resolution(value: Any, active: set[int]) -> int:
    identity = id(value)
    if identity in active:
        msg = "cyclic values cannot be resolved"
        raise ValueError(msg)
    active.add(identity)
    return identity


def _materialize_factory(config: FactoryConfig, active: set[int]) -> Any:
    identity = _enter_resolution(config, active)
    try:
        values = {
            field_name: _resolve_value(getattr(config, field_name), active)
            for field_name in config.factory_fields
        }
        return config.factory_target(**values)
    finally:
        active.remove(identity)


def _resolve_model_instance(model: BaseModel, active: set[int]) -> BaseModel:
    identity = _enter_resolution(model, active)
    try:
        model_type = type(model)
        resolved_type = _resolved_model_type(model_type, force=True)
        values = {
            field_name: _resolve_value(getattr(model, field_name), active)
            for field_name in model_type.model_fields
        }
        if model.model_extra:
            values.update(
                {
                    key: _resolve_value(value, active)
                    for key, value in model.model_extra.items()
                }
            )
        return resolved_type.model_validate(values, by_alias=True, by_name=True)
    finally:
        active.remove(identity)


def _resolve_value(value: Any, active: set[int]) -> Any:
    if isinstance(value, FactoryConfig):
        return _materialize_factory(value, active)
    if isinstance(value, BaseModel):
        return _resolve_model_instance(value, active)
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


def _model_resolve(config: BaseConfig) -> BaseConfig:
    token = _DISABLE_CLI_PARSE_ARGS.set(True)
    try:
        return cast(BaseConfig, _resolve_model_instance(config, set()))
    finally:
        _DISABLE_CLI_PARSE_ARGS.reset(token)
