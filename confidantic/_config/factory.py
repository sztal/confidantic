"""Public factory models and their Pydantic validation and serialization hooks.

Constructor inspection lives in ``_factory_build``; value and annotation
resolution live in ``_factory_resolution``. Public methods import those modules
lazily so their collaborators can refer to the fully defined ``Factory`` class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import (
    Any,
    ClassVar,
    Generic,
    TypeVar,
    cast,
    overload,
)

from pydantic import GetCoreSchemaHandler
from pydantic._internal._mock_val_ser import MockValSer
from pydantic_core import (
    CoreSchema,
    PydanticCustomError,
    core_schema,
)

from confidantic._config._cli import _CliSettings
from confidantic._config._options import ConfigModelDict
from confidantic._config._settings import wrap_settings_schema
from confidantic._config.base import BaseConfig

__all__ = ("Factory",)

T = TypeVar("T")
U = TypeVar("U")


def _factory_target(factory_type: type[Any]) -> type[Any] | None:
    """Read a concrete target or the target argument of a generic specialization.

    Explicit or inherited ``factory_target`` metadata takes precedence. Otherwise
    a single class-valued generic argument supplies the target; an unresolved
    TypeVar or absent specialization returns None without constructing a model.
    """
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
    """Identify factory classes without accepting their instances."""
    return isinstance(value, type) and issubclass(value, Factory)


def _serialize_factory(value: Any, handler: Any) -> Any:
    """Preserve factory classes and delegate instance serialization to Pydantic."""
    if _is_factory_type(value):
        return value
    return handler(value)


class _DeferredFactorySchema(MockValSer[Any]):
    """Keep Pydantic's deferred validator/serializer pickleable.

    Pickle probes __setstate__ before restoring slots. The upstream proxy would
    attempt a rebuild with its own slots still missing and recurse indefinitely.
    All actual validator/serializer accesses retain Pydantic's lazy rebuilding.
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        if name == "__setstate__":
            raise AttributeError(name)
        return super().__getattr__(name)


class Factory(BaseConfig, Generic[T]):
    """Configuration generated from a target type's constructor.

    Concrete subclasses are created with :meth:`model_from`. Their fields
    correspond to annotated constructor parameters and validated instances can
    create the target object by calling :meth:`model_resolve`.

    In lax validation, Pydantic fields convert compatible target instances to
    generated factory instances and target classes to generated factory classes.
    Existing compatible factory instances and classes are retained without
    field revalidation. Mappings undergo model validation. Strict validation
    does not perform the target-class or target-instance conversions and rejects
    factory classes. Both modes check the target compatibility of instances.

    Attributes
    ----------
    factory_target
        Target class constructed during resolution.
    factory_fields
        Constructor field names forwarded as keyword arguments during
        resolution. Additional fields declared on a factory subclass are not
        forwarded to the target by :meth:`model_resolve`. Make serialization
        includes only constructor fields and uses their canonical keyword names.
        Serialization filters and field serializers still apply; ambiguous
        serialized constructor keys raise an error.
    """

    factory_target: ClassVar[type[T]]
    factory_fields: ClassVar[tuple[str, ...]] = ()
    model_config: ClassVar[ConfigModelDict] = ConfigModelDict(defer_build=True)

    _factory_strict: ClassVar[bool] = True
    _factory_types_namespace: ClassVar[Mapping[str, Any] | None] = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Preserve deferred generic bases when generated classes are serialized."""
        super().__pydantic_init_subclass__(**kwargs)
        for kind in ("validator", "serializer"):
            attribute = f"__pydantic_{kind}__"
            deferred = cls.__dict__.get(attribute)
            if isinstance(deferred, MockValSer):
                setattr(
                    cls,
                    attribute,
                    _DeferredFactorySchema(
                        deferred._error_message,
                        code=deferred._code,
                        val_or_ser=kind,
                        attempt_rebuild=deferred._attempt_rebuild,
                    ),
                )

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Build target-aware lax and strict validation with shared serialization.

        Parameters
        ----------
        source_type
            Factory annotation supplied by Pydantic. A generic specialization
            obtains constructor fields from a generated concrete factory model.
        handler
            Generator for the model schema wrapped with settings-source assembly.

        Returns
        -------
        CoreSchema
            Lax/strict schema checking target compatibility. Lax validation can
            convert target classes and instances; strict validation accepts model
            input and compatible factory instances. Both branches delegate
            instance serialization while preserving factory class values.

        Notes
        -----
        Specialized schemas are copied before use so serialized schema state
        can be restored independently. Compatible existing factories bypass
        field revalidation in the lax branch.
        """
        target = _factory_target(cls) or _factory_target(source_type)
        generic_arguments = getattr(cls, "__pydantic_generic_metadata__", {}).get(
            "args", ()
        )
        schema = wrap_settings_schema(
            cls.model_from(target)
            if target is not None and generic_arguments
            else source_type,
            handler,
        )
        if target is not None and generic_arguments:
            # Shared schema dictionaries can restore a SchemaSerializer before
            # its schema is populated during unpickling.
            schema = deepcopy(schema)

        def check_target(value: Any) -> Any:
            """Retain a factory only if its recorded target satisfies this annotation."""
            value_target = _factory_target(
                type(value) if isinstance(value, Factory) else value
            )
            if target is not None and (
                value_target is None or not issubclass(value_target, target)
            ):
                raise PydanticCustomError(
                    "factory",
                    "Input should be a Factory for the expected target type",
                )
            return value

        def validate(value: Any, next_validator: Callable[[Any], Any]) -> Any:
            """Retain compatible factories, validate mappings, or generate from targets.

            Conversion TypeError and ValueError become the annotation's custom
            factory error. Mapping validation keeps the normal model errors.
            """
            if isinstance(value, Factory) or _is_factory_type(value):
                return check_target(value)
            if isinstance(value, Mapping):
                return next_validator(value)
            try:
                value_target = value if isinstance(value, type) else type(value)
                if target is not None and not issubclass(value_target, target):
                    raise TypeError
                if isinstance(value, type):
                    return Factory.model_from(
                        value,
                        __strict__=cls._factory_strict,
                        __types_namespace__=cls._factory_types_namespace,
                    )
                return Factory.model_from(
                    value,
                    __strict__=cls._factory_strict,
                    __types_namespace__=cls._factory_types_namespace,
                )()
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
        return core_schema.lax_or_strict_schema(
            lax_schema,
            core_schema.no_info_after_validator_function(check_target, strict_schema),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                _serialize_factory, schema=schema
            ),
        )

    @classmethod
    @overload
    def model_from(
        cls,
        source: type[U],
        *args: Any,
        __name__: str | None = None,
        __recursive__: type[Any] | Callable[[Any], bool] | None = None,
        __strict__: bool = True,
        __types_namespace__: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> type[Factory[U]]: ...

    @classmethod
    @overload
    def model_from(
        cls,
        source: U,
        *,
        __name__: str | None = None,
        __recursive__: type[Any] | Callable[[Any], bool] | None = None,
        __strict__: bool = True,
        __types_namespace__: Mapping[str, Any] | None = None,
    ) -> type[Factory[U]]: ...

    @classmethod
    def model_from(
        cls,
        source: type[Any] | Any,
        *args: Any,
        __name__: str | None = None,
        __recursive__: type[Any] | Callable[[Any], bool] | None = None,
        __strict__: bool = True,
        __types_namespace__: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a concrete factory config from a target type or instance.

        Annotated positional-or-keyword and keyword-only constructor parameters
        define the generated fields. Unannotated parameters are omitted by
        default; ``*args`` and ``**kwargs`` are always omitted. Positional-only
        parameters that would become fields are rejected because resolution
        calls the constructor by keyword. An
        omitted unannotated required parameter can consequently cause a
        constructor ``TypeError`` at resolution time.

        When ``source`` is an instance, attributes with matching parameter names
        replace constructor defaults. Missing attributes retain those defaults,
        or leave a field required if no default exists. Factory instances,
        mutable collections, and unhashable defaults are deep-copied for each
        configuration through generated field default factories. Their templates
        still participate in settings-source merging. Other hashable objects retain normal
        Pydantic default behavior; explicit inputs undergo normal validation.

        Parameters
        ----------
        source
            Target type, or an instance whose type and current attribute values
            define the generated configuration model.
        __name__
            Optional generated model name. By default, append ``Config`` to the
            target type name.
        __recursive__
            Optional type, type hint, or predicate used to convert matching
            default values into nested factory fields, recursively inspecting
            their constructors. Type hints use strict Pydantic validation for
            matching and exclude ``None``; predicates receive the default value.
            Existing factories are skipped. Required fields without a source
            value remain unchanged. Matching union branches are replaced while
            unrelated alternatives are retained. Selection examines each
            parameter's whole default, not elements inside collection defaults.
            Callable typing forms, including ``typing.Optional[T]``,
            ``Annotated[T, ...]``, and ``NewType``, use type matching without
            invoking their constructors.
        __strict__
            Whether unresolved annotation names raise NameError. If False,
            unresolved annotations and unannotated parameters become Any fields,
            without type validation or conversion. A partially unresolved
            annotation becomes Any as a whole. Defaults and requiredness are
            preserved. Malformed annotations and schema errors still propagate.
            This controls annotation resolution, not Pydantic validation strictness.
        __types_namespace__
            Names taking precedence over automatic constructor annotation lookup.
            The mapping is shallow-copied; already evaluated type objects are
            unchanged. Both generation options apply recursively and are retained
            by generated models for validation-time target conversion and rebuilds.
            New explicit model_from calls use their own supplied options or defaults.
        *args, **kwargs
            Arguments used to construct ``source`` when it is a type. The
            resulting instance values become generated defaults. With no
            arguments, the target is not constructed. These arguments are not
            configuration-field overrides; use :meth:`instance_from` for those.

        Returns
        -------
        type[Factory[U]]
            Generated concrete configuration class. It is not registered as
            an importable module attribute.

        Raises
        ------
        TypeError
            If constructor arguments accompany an instance, the target is
            incompatible with a specialized factory, or an annotated parameter
            is positional-only. Constructor and annotation errors propagate.
        NameError
            If a field annotation contains an unresolved name and __strict__ is True.
        """
        if isinstance(source, type):
            target = source
            instance = source(*args, **kwargs) if args or kwargs else None
        else:
            if args or kwargs:
                msg = "constructor arguments require a target type as source"
                raise TypeError(msg)
            target = type(source)
            instance = source
        expected_target = _factory_target(cls)
        if expected_target is not None and not issubclass(target, expected_target):
            msg = f"{cls.__name__} expects {expected_target.__name__}"
            raise TypeError(msg)
        factory_base = (
            cast(type[Factory[Any]], Factory.__class_getitem__(target))
            if cls is Factory
            else cls
        )
        from confidantic._config._factory_build import _FactoryModelBuilder

        return _FactoryModelBuilder(
            factory_base,
            target,
            instance=instance,
            recursive_selector=__recursive__,
            strict=__strict__,
            types_namespace=__types_namespace__,
        ).build(name=__name__)

    @classmethod
    def instance_from(
        cls,
        source: type[U] | U,
        *,
        __name__: str | None = None,
        __strict__: bool = True,
        __types_namespace__: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Factory[U]:
        """Create a new factory config instance from a source.

        Generate the class with :meth:`model_from`, then construct it using
        normal settings sources. Keyword arguments are configuration inputs,
        so higher-priority sources such as CLI input can override them.
        To supply constructor arguments or enable recursive default generation,
        call :meth:`model_from` separately and instantiate its result.

        Parameters
        ----------
        source
            Target type or instance used to generate the configuration model.
        __name__
            Optional generated model name.
        __strict__
            Annotation-resolution policy passed to model_from, independent of
            Pydantic validation strictness. False includes untyped parameters
            and replaces unresolved field annotations with Any.
        __types_namespace__
            Explicit annotation names passed to model_from with highest priority.
        **kwargs
            Values for the generated fields. Unspecified fields use their
            defaults after consulting configured settings sources.

        Returns
        -------
        Factory[U]
            New factory config instance.
        """
        return cast(
            Factory[U],
            cls.model_from(
                source,
                __name__=__name__,
                __strict__=__strict__,
                __types_namespace__=__types_namespace__,
            )(**kwargs),
        )

    def model_resolve(self) -> T:  # type: ignore[override]
        """Create the target object from the validated configuration values.

        Traversal starts from ``factory_fields``; additional fields and extras
        on this factory are ignored. Within those constructor inputs, nested
        factory instances and classes are resolved recursively in Pydantic model
        fields and extras, mapping keys and values, lists, tuples, sets, and
        frozensets. Factory classes are instantiated with their defaults first.
        Mappings become dictionaries and nested Pydantic models are rebuilt and
        validated. Other objects are passed through unchanged.

        Only ``factory_fields`` are passed to the target, as keyword arguments.
        Each call invokes the target constructor; instance identity is subject
        to that constructor's behavior. CLI parsing is disabled throughout
        resolution, including configuration models constructed by the target;
        other settings sources remain active.

        Returns
        -------
        T
            Instance of the target type recorded by :meth:`model_from`.

        Raises
        ------
        ValueError
            If recursive traversal encounters a cycle. Nested validation and
            target constructor errors also propagate.

        Notes
        -----
        Factory field values are not revalidated before calling the target.
        In particular, ``model_construct`` and unchecked ``model_copy`` updates
        can supply invalid scalar values. Traversed containers and models are
        rebuilt, while arbitrary objects remain shared. Repeated occurrences
        of the same factory invoke its target separately; aliasing is not
        preserved. Self-referential and mutually recursive Pydantic model
        annotations are supported for acyclic values. Generated model types are
        reused within the resolution call without modifying the original types.
        """
        from confidantic._config._factory_resolution import _FactoryResolver

        with _CliSettings.suppress():
            return cast(T, _FactoryResolver().resolve(self))
