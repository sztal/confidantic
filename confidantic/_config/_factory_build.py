"""Generate factory fields from constructor annotations and concrete defaults.

A builder belongs to one ``Factory.model_from`` operation. Recursive generation
creates independent builders; generated models retain only field definitions and
copied-default templates, never the builder itself.
"""

from __future__ import annotations

import sys
from collections.abc import (
    Callable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
)
from functools import reduce
from inspect import Parameter, signature
from operator import or_
from types import SimpleNamespace, UnionType
from typing import (
    Annotated,
    Any,
    NewType,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import ConfigDict, Field, TypeAdapter, create_model
from pydantic.errors import PydanticUserError
from pydantic_core import PydanticUndefined

from confidantic._config._settings import _CopiedDefault
from confidantic._config.factory import (
    Factory,
    _constructor_signature,
    _FieldSelector,
    _is_factory_type,
)


class _FactoryModelBuilder:
    """Build one concrete factory class without modifying its source template.

    Parameters
    ----------
    factory_type
        Selected factory base, already checked for target compatibility.
    target
        Class whose annotated constructor parameters define the fields.
    instance
        Optional template supplying defaults from matching attributes.
    recursive_selector
        Type hint or predicate selecting concrete defaults for nested generation.
        ``None`` leaves their annotations and defaults unchanged.
    strict
        Reject unresolved annotations; otherwise use Any and include untyped fields.
    types_namespace
        Explicit names taking precedence over automatic annotation lookup.
    include, exclude
        Mutually exclusive selectors for this target's configured parameters.

    Notes
    -----
    Construction records these inputs without inspecting or instantiating the
    target. ``build`` creates field definitions locally and assigns constructor
    metadata only to the new class. Annotation, selector, constructor, and
    Pydantic errors propagate to the caller.
    """

    def __init__(
        self,
        factory_type: type[Factory[Any]],
        target: type[Any],
        *,
        instance: object | None,
        recursive_selector: type[Any] | Callable[[Any], bool] | None,
        strict: bool = True,
        types_namespace: Mapping[str, Any] | None = None,
        include: _FieldSelector | None = None,
        exclude: _FieldSelector | None = None,
    ) -> None:
        if include is not None and exclude is not None:
            raise ValueError("__include__ and __exclude__ are mutually exclusive")
        self.include = frozenset(include) if isinstance(include, set) else include
        self.exclude = frozenset(exclude) if isinstance(exclude, set) else exclude
        self.selector = self.include if self.include is not None else self.exclude
        self.selector_arity = 1
        if isinstance(self.selector, frozenset):
            if not all(isinstance(name, str) for name in self.selector):
                raise TypeError("field selector names must be strings")
        elif self.selector is not None:
            message = (
                "field selector must accept exactly one or two positional arguments"
            )
            if not callable(self.selector):
                raise TypeError(message)
            try:
                if sys.version_info >= (3, 14):
                    from annotationlib import Format

                    selector_signature = signature(
                        self.selector, annotation_format=Format.FORWARDREF
                    )
                else:
                    selector_signature = signature(self.selector)
            except (TypeError, ValueError) as error:
                raise TypeError(message) from error
            arities = []
            for count in (1, 2):
                try:
                    selector_signature.bind(*([None] * count))
                except TypeError:
                    continue
                arities.append(count)
            if len(arities) != 1 or any(
                parameter.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
                for parameter in selector_signature.parameters.values()
            ):
                raise TypeError(message)
            self.selector_arity = arities[0]
        self.factory_type = factory_type
        self.target = target
        self.instance = instance
        self.recursive_selector = recursive_selector
        self.strict = strict
        self.types_namespace = (
            dict(types_namespace) if types_namespace is not None else {}
        )

    def build(self, *, name: str | None = None) -> type[Factory[Any]]:
        """Inspect the constructor and generate a class with ordered fields.

        Parameters
        ----------
        name
            Class name; defaults to the target name followed by ``Config``.

        Returns
        -------
        type[Factory[Any]]
            New subclass with constructor field names and target metadata. The
            class is not registered as a module attribute.

        Raises
        ------
        TypeError
            If an annotated constructor parameter is positional-only. Errors
            from annotation evaluation and nested generation also propagate.
        """
        init = self.target.__init__
        namespace: dict[str, Any] = {}
        # Inherited constructors can refer to names in their defining modules.
        for base in reversed(self.target.__mro__):
            module = sys.modules.get(base.__module__)
            if module is not None:
                namespace.update(vars(module))
        namespace.update(getattr(init, "__globals__", {}))
        namespace.update(self.types_namespace)
        # Distinct locals force cached ForwardRefs to re-evaluate on Python 3.11-3.13.
        local_namespace = namespace.copy()
        parameters = _constructor_signature(self.target).parameters
        named_parameters = {
            name
            for name, parameter in parameters.items()
            if parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        }
        if isinstance(self.selector, frozenset):
            unknown = self.selector - named_parameters
            if unknown:
                raise ValueError(
                    f"unknown constructor fields: {', '.join(sorted(unknown))}"
                )
        fields: dict[str, tuple[Any, Any]] = {}
        excluded: set[str] = set()

        for field_name, parameter in parameters.items():
            if parameter.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                continue
            if self.selector_arity == 1 and not self.selects(field_name):
                excluded.add(field_name)
                continue
            raw_annotation = (
                Parameter.empty
                if getattr(init, "__no_type_check__", False)
                else parameter.annotation
            )
            if raw_annotation is Parameter.empty and self.strict:
                continue
            annotation = Any
            if raw_annotation is not Parameter.empty:
                # Resolve only this field, without evaluating return/variadic hints
                # or discarding valid fields when another name is unavailable.
                hint = SimpleNamespace(
                    __annotations__={field_name: raw_annotation},
                    __type_params__=getattr(init, "__type_params__", ()),
                )
                try:
                    annotation = get_type_hints(
                        hint,
                        globalns=namespace,
                        localns=local_namespace,
                        include_extras=True,
                    )[field_name]
                except NameError as error:
                    if self.strict:
                        msg = (
                            f"{self.target.__qualname__}.__init__ parameter "
                            f"{field_name!r}: {error}"
                        )
                        raise NameError(msg, name=error.name) from error

            if self.selector_arity == 2 and not self.selects(field_name, annotation):
                excluded.add(field_name)
                continue
            if parameter.kind is Parameter.POSITIONAL_ONLY:
                msg = (
                    f"{self.target.__qualname__}.__init__ parameter {field_name!r} "
                    "is positional-only"
                )
                raise TypeError(msg)
            if field_name == "instance":
                raise TypeError(
                    "exclude reserved field 'instance' and pass it to .instance(instance=...)"
                )
            default = parameter.default
            if self.instance is not None and hasattr(self.instance, field_name):
                default = getattr(self.instance, field_name)
            if (
                self.recursive_selector is not None
                and default is not Parameter.empty
                and self.matches_selector(default)
            ):
                # A nested target need not match the specialized outer factory.
                factory_type = Factory.model_from(
                    default,
                    __recursive__=self.recursive_selector,
                    __strict__=self.strict,
                    __types_namespace__=self.types_namespace,
                )
                annotation = self.replace_annotation(annotation, default, factory_type)
                default = factory_type()
            if default is Parameter.empty:
                default = PydanticUndefined
            else:
                # Factory templates can hold mutable values despite being hashable.
                copy_default = isinstance(
                    default,
                    Factory | MutableMapping | MutableSequence | MutableSet | bytearray,
                )
                if not copy_default:
                    try:
                        hash(default)
                    except TypeError:
                        copy_default = True
                if copy_default:
                    default = Field(default_factory=_CopiedDefault(default))
            fields[field_name] = (annotation, default)

        conflicts = excluded & self.factory_type.model_fields.keys()
        if conflicts:
            raise ValueError(
                f"cannot exclude inherited model fields: {', '.join(sorted(conflicts))}"
            )
        model = create_model(
            name or f"{self.target.__name__}Config",
            __base__=self.factory_type,
            __module__=Factory.__module__,
            **cast(dict[str, Any], fields),
        )
        model.factory_target = self.target
        model.factory_fields = tuple(fields)
        model._factory_strict = self.strict
        model._factory_types_namespace = self.types_namespace
        model._factory_include = self.include
        model._factory_exclude = self.exclude
        # Generic bases are deferred so their cached schema never captures a
        # call's policy. Concrete factories still report schema errors eagerly.
        model.model_rebuild(force=True)
        return model

    def selects(self, name: str, annotation: Any = Any) -> bool:
        """Evaluate the selected predicate once for a constructor parameter."""
        if self.selector is None:
            return True
        if isinstance(self.selector, frozenset):
            matched = name in self.selector
        else:
            predicate = cast(Callable[..., bool], self.selector)
            matched = bool(
                predicate(name)
                if self.selector_arity == 1
                else predicate(annotation, name)
            )
        return matched if self.include is not None else not matched

    def replace_annotation(
        self,
        annotation: Any,
        value: Any,
        factory_type: type[Factory[Any]],
    ) -> Any:
        """Replace matching union branches, preserving alternatives and metadata.

        Parameters
        ----------
        annotation
            Constructor annotation to rewrite. Union branches and the underlying
            type of Annotated are visited recursively; metadata is retained.
        value
            Concrete default used to select branches by strict type validation.
        factory_type
            Generated factory class to substitute for matching annotations.

        Returns
        -------
        Any
            Rewritten annotation, retaining branches that do not match. Generic
            containers are matched as whole types rather than by their elements.
        """
        origin = get_origin(annotation)
        arguments = get_args(annotation)
        if origin in (Union, UnionType) and arguments:
            replaced_arguments = tuple(
                self.replace_annotation(argument, value, factory_type)
                for argument in arguments
            )
            if replaced_arguments == arguments:
                return annotation
            copy_with = getattr(annotation, "copy_with", None)
            if copy_with is not None:
                return copy_with(replaced_arguments)
            if origin is UnionType:
                return reduce(or_, replaced_arguments)
            return origin[replaced_arguments]
        if origin is Annotated and arguments:
            underlying = self.replace_annotation(arguments[0], value, factory_type)
            if underlying == arguments[0]:
                return annotation
            return Annotated[underlying, *arguments[1:]]
        if self.matches_type_hint(value, annotation):
            return factory_type
        return annotation

    def matches_selector(self, value: Any) -> bool:
        """Select whole defaults, skipping existing factories before predicates.

        Type hints, including callable typing forms, use strict validation.
        Other callable selectors receive the value and their result is converted
        to bool. Predicate exceptions propagate; only type-hint matching excludes
        None automatically.
        """
        if isinstance(value, Factory) or _is_factory_type(value):
            return False
        selector = self.recursive_selector
        if isinstance(selector, (type, NewType)) or get_origin(selector) is not None:
            return self.matches_type_hint(value, selector)
        if callable(selector):
            return bool(selector(value))
        return self.matches_type_hint(value, selector)

    @staticmethod
    def matches_type_hint(value: Any, type_hint: Any) -> bool:
        """Test a non-None value against a type hint without accepting coercion.

        Parameters
        ----------
        value
            Concrete default to test; ``None`` always returns False.
        type_hint
            Annotation used to construct a TypeAdapter. Arbitrary types are
            allowed unless the annotated type supplies its own configuration.

        Returns
        -------
        bool
            Whether strict validation succeeds. TypeError and ValueError from
            validation count as a mismatch; adapter construction errors propagate
            except for the retried model-owned configuration case.
        """
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
