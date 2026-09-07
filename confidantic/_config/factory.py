"""Configuration models generated from object constructors."""

from __future__ import annotations

import sys
from collections.abc import (
    Callable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
)
from copy import copy, deepcopy
from functools import reduce
from inspect import Parameter, signature
from operator import or_
from types import UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    Self,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    GetCoreSchemaHandler,
    TypeAdapter,
    create_model,
)
from pydantic.errors import PydanticUserError
from pydantic.fields import FieldInfo
from pydantic_core import (
    CoreSchema,
    PydanticCustomError,
    PydanticUndefined,
    core_schema,
)
from typing_extensions import TypeAliasType

from confidantic._config.base import (
    _DISABLE_CLI_PARSE_ARGS,
    BaseConfig,
)
from confidantic.utils import import_from_string, make

__all__ = ("Factory", "FactoryField")

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


def _is_factory_type(value: Any) -> bool:
    return isinstance(value, type) and issubclass(value, Factory)


class Factory(BaseConfig, Generic[T]):
    """Configuration generated from a target type's constructor.

    Concrete subclasses are created with :meth:`model_from`. Their fields
    correspond to annotated constructor parameters and validated instances can
    create the target object by calling :meth:`model_resolve`.

    Pydantic fields accept target instances and convert them to generated
    factory config instances. Mappings supplied to concrete factory config
    fields retain normal Pydantic model validation.
    """

    factory_target: ClassVar[type[T]]
    factory_fields: ClassVar[tuple[str, ...]] = ()

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
                if target is not None and not issubclass(value.factory_target, target):
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
    @overload
    def model_from(
        cls,
        source: type[U],
        *,
        name: str | None = None,
        as_factory: type[Any] | Callable[[Any], bool] | None = None,
    ) -> type[Factory[U]]: ...

    @classmethod
    @overload
    def model_from(
        cls,
        source: U,
        *,
        name: str | None = None,
        as_factory: type[Any] | Callable[[Any], bool] | None = None,
    ) -> type[Factory[U]]: ...

    @classmethod
    def model_from(
        cls,
        source: type[Any] | Any,
        *,
        name: str | None = None,
        as_factory: type[Any] | Callable[[Any], bool] | None = None,
    ) -> Any:
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
            Optional generated model name. By default, append ``Config`` to the
            target type name.
        as_factory
            Optional type, type hint, or predicate used to convert matching
            default values into nested factory fields.

        Returns
        -------
        type[Factory[U]]
            Generated concrete configuration class.
        """
        target = source if isinstance(source, type) else type(source)
        expected_target = _factory_target(cls)
        if expected_target is not None and not issubclass(target, expected_target):
            msg = f"{cls.__name__} expects {expected_target.__name__}"
            raise TypeError(msg)
        instance = None if isinstance(source, type) else source
        factory_base = (
            cast(type[Factory[Any]], Factory.__class_getitem__(target))
            if cls is Factory
            else cls
        )
        return factory_base._model_from(
            instance, target, name=name, as_factory=as_factory
        )

    @classmethod
    def instance_from(
        cls, source: type[U] | U, *, name: str | None = None, **kwargs: Any
    ) -> Factory[U]:
        """Create a new factory config instance from a source.

        Parameters
        ----------
        source
            Target type or instance used to generate the configuration model.
        name
            Optional generated model name.
        **kwargs
            Values for the generated fields. Unspecified fields use their
            default values.

        Returns
        -------
        Factory[U]
            New factory config instance.
        """
        return cast(Factory[U], cls.model_from(source, name=name)(**kwargs))

    def model_resolve(  # type: ignore[override]
        self,
        updates: Mapping[str, Any] | None = None,
        *,
        recursive: bool = True,
        **kwargs: Any,
    ) -> T:
        """Create the target object from the validated configuration values.

        CLI parsing is disabled throughout resolution, including any
        configuration models constructed by the target.

        Parameters
        ----------
        updates
            Optional field values to validate before resolving the target.
            Keyword updates override entries with the same field name.
        recursive
            Whether nested factories and factories in containers are resolved
            after the updates have been applied.
        **kwargs
            Additional field values to validate before resolving the target.

        Returns
        -------
        T
            Instance of the target type recorded by :meth:`model_from`.
        """
        values = dict(updates or {})
        values.update(kwargs)
        config = self if not values else self.copy(**values)
        token = _DISABLE_CLI_PARSE_ARGS.set(True)
        try:
            return cast(T, _resolve_factory(config, set(), recursive=recursive))
        finally:
            _DISABLE_CLI_PARSE_ARGS.reset(token)

    @classmethod
    def _model_from(
        cls,
        instance: object | None,
        target: type[T],
        *,
        name: str | None,
        as_factory: type[Any] | Callable[[Any], bool] | None,
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
            source_default = default
            if (
                as_factory is not None
                and source_default is not Parameter.empty
                and _matches_factory_selector(source_default, as_factory)
            ):
                factory_type = Factory.model_from(source_default, as_factory=as_factory)
                fields[field_name] = (factory_type, factory_type())
                continue
            if default is Parameter.empty:
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


class _FactoryFieldMetadata:
    def __get_pydantic_core_schema__(
        self,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        factory_type = get_args(source_type)[0]
        target = factory_type.__pydantic_generic_metadata__["args"][0]
        schema = handler(source_type)

        def validate(value: Any, next_validator: Callable[[Any], Any]) -> Any:
            try:
                if isinstance(value, Factory):
                    raise TypeError
                if isinstance(value, str):
                    value = import_from_string(value)
                    if callable(value) and not isinstance(value, type):
                        value = value()
                elif isinstance(value, Mapping) and "@call" in value:
                    value = make(value)
                elif callable(value) and not isinstance(value, type):
                    value = value()
                if isinstance(value, type) and issubclass(value, Factory):
                    if not issubclass(value.factory_target, target):
                        raise TypeError
                    return value
                value_target = value if isinstance(value, type) else type(value)
                if not issubclass(value_target, target):
                    raise TypeError
                factory_base = cast(
                    type[Factory[Any]], Factory.__class_getitem__(target)
                )
                return next_validator(factory_base.model_from(value))
            except (TypeError, ValueError) as error:
                raise PydanticCustomError(
                    "factory_field",
                    "Input should be a compatible target or Factory type",
                ) from error

        return core_schema.no_info_wrap_validator_function(validate, schema)


#: A Pydantic annotation for fields storing generated factory classes. Values may
#: be compatible factory classes, target classes or instances, import strings,
#: callables, or call/make mappings. Validation produces ``type[Factory[T]]``.
FactoryField = TypeAliasType(
    "FactoryField",
    Annotated[type[Factory[T]], _FactoryFieldMetadata()],
    type_params=(T,),
)


def _matches_factory_selector(
    value: Any,
    selector: Any,
) -> bool:
    if isinstance(value, Factory) or _is_factory_type(value):
        return False
    if isinstance(selector, type):
        return _matches_factory_type_hint(value, selector)
    if callable(selector):
        return bool(selector(value))
    return _matches_factory_type_hint(value, selector)


def _matches_factory_type_hint(value: Any, type_hint: Any) -> bool:
    if value is None:
        return False
    try:
        adapter = TypeAdapter(
            type_hint, config=ConfigDict(arbitrary_types_allowed=True)
        )
    except PydanticUserError as error:
        if error.code != "type-adapter-config-unused":
            raise
        adapter = TypeAdapter(type_hint)
    try:
        adapter.validate_python(value, strict=True)
    except (TypeError, ValueError):
        return False
    return True


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


def _resolved_annotation(annotation: Any) -> Any:
    if isinstance(annotation, type):
        if issubclass(annotation, Factory):
            target = _factory_target(annotation)
            return target if target is not None else annotation
        if issubclass(annotation, BaseModel):
            return _resolved_model_type(annotation)
        return annotation

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if getattr(origin, "__name__", None) == "FactoryField":
        return arguments[0]
    if origin is None or not arguments:
        return annotation

    resolved_arguments = tuple(_resolved_annotation(argument) for argument in arguments)
    if resolved_arguments == arguments:
        return annotation
    copy_with = getattr(annotation, "copy_with", None)
    if copy_with is not None:
        return copy_with(resolved_arguments)
    if origin is UnionType:
        return reduce(or_, resolved_arguments)
    return origin[resolved_arguments]


def _resolved_field(field: FieldInfo, annotation: Any) -> FieldInfo:
    resolved = copy(field)
    resolved.annotation = annotation
    return resolved


def _resolved_model_type(
    source: type[BaseModel],
    *,
    force: bool = False,
    name: str | None = None,
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, field in source.model_fields.items():
        annotation = _resolved_annotation(field.annotation)
        if annotation != field.annotation:
            fields[field_name] = (annotation, _resolved_field(field, annotation))
    if not fields and not force:
        return source
    return cast(
        type[BaseModel],
        create_model(
            name or f"{source.__name__}Resolved",
            __base__=source,
            __module__=source.__module__,
            **cast(dict[str, Any], fields),
        ),
    )


def _resolve_factory(
    config: Factory[Any],
    active: set[int],
    *,
    recursive: bool = True,
) -> Any:
    identity = _enter_resolution(config, active)
    try:
        values = {
            field_name: _resolve_value(
                getattr(config, field_name), active, recursive=recursive
            )
            for field_name in config.factory_fields
        }
        return config.factory_target(**values)
    finally:
        active.remove(identity)


def _resolve_model_instance(
    model: BaseModel,
    active: set[int],
    *,
    recursive: bool = True,
    name: str | None = None,
) -> BaseModel:
    identity = _enter_resolution(model, active)
    try:
        model_type = type(model)
        resolved_type = _resolved_model_type(model_type, force=True, name=name)
        values = {}
        for field_name in model_type.model_fields:
            value = getattr(model, field_name)
            factory = value if isinstance(value, Factory) else None
            if factory is None and _is_factory_type(value):
                factory = value()
            if factory is not None:
                values[field_name] = _resolve_factory(
                    factory, active, recursive=recursive
                )
            else:
                values[field_name] = _resolve_value(value, active, recursive=recursive)
        if model.model_extra:
            values.update(
                {
                    key: _resolve_value(value, active, recursive=recursive)
                    for key, value in model.model_extra.items()
                }
            )
        return resolved_type.model_validate(values, by_alias=True, by_name=True)
    finally:
        active.remove(identity)


def _contains_factory(value: Any, seen: set[int] | None = None) -> bool:
    if isinstance(value, Factory):
        return True
    if _is_factory_type(value):
        return True
    if seen is None:
        seen = set()
    if isinstance(value, BaseModel | Mapping | list | tuple | set | frozenset):
        identity = id(value)
        if identity in seen:
            return False
        seen.add(identity)
    if isinstance(value, BaseModel):
        return any(
            _contains_factory(getattr(value, field_name), seen)
            for field_name in type(value).model_fields
        ) or any(
            _contains_factory(item, seen) for item in (value.model_extra or {}).values()
        )
    if isinstance(value, Mapping):
        return any(
            _contains_factory(key, seen) or _contains_factory(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_factory(item, seen) for item in value)
    return False


def _resolve_value(
    value: Any,
    active: set[int],
    *,
    recursive: bool = True,
) -> Any:
    if isinstance(value, Factory):
        if not recursive:
            return value
        return _resolve_factory(value, active, recursive=recursive)
    if _is_factory_type(value):
        if not recursive:
            return value
        return _resolve_factory(value(), active, recursive=recursive)
    if isinstance(value, BaseModel):
        if not recursive:
            return value
        return _resolve_model_instance(value, active, recursive=recursive)
    if isinstance(value, Mapping):
        identity = _enter_resolution(value, active)
        try:
            return {
                _resolve_value(key, active, recursive=recursive): _resolve_value(
                    item, active, recursive=recursive
                )
                for key, item in value.items()
            }
        finally:
            active.remove(identity)
    if isinstance(value, list):
        identity = _enter_resolution(value, active)
        try:
            return [_resolve_value(item, active, recursive=recursive) for item in value]
        finally:
            active.remove(identity)
    if isinstance(value, tuple):
        identity = _enter_resolution(value, active)
        try:
            return tuple(
                _resolve_value(item, active, recursive=recursive) for item in value
            )
        finally:
            active.remove(identity)
    if isinstance(value, set):
        identity = _enter_resolution(value, active)
        try:
            return {_resolve_value(item, active, recursive=recursive) for item in value}
        finally:
            active.remove(identity)
    if isinstance(value, frozenset):
        identity = _enter_resolution(value, active)
        try:
            return frozenset(
                _resolve_value(item, active, recursive=recursive) for item in value
            )
        finally:
            active.remove(identity)
    return value
