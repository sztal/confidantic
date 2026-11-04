"""Generate factory fields from constructor annotations and concrete defaults.

A builder belongs to one ``Factory.model_from`` operation. Recursive generation
creates independent builders; generated models retain only field definitions and
copied-default templates, never the builder itself.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, MutableMapping, MutableSequence, MutableSet
from functools import reduce
from inspect import Parameter, signature
from operator import or_
from types import UnionType
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
from confidantic._config.factory import Factory, _is_factory_type


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
    ) -> None:
        self.factory_type = factory_type
        self.target = target
        self.instance = instance
        self.recursive_selector = recursive_selector

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
        annotations = get_type_hints(
            init, globalns=namespace, localns=namespace, include_extras=True
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
                    f"{self.target.__qualname__}.__init__ parameter {field_name!r} "
                    "is positional-only"
                )
                raise TypeError(msg)
            if parameter.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                continue

            default = parameter.default
            if self.instance is not None and hasattr(self.instance, field_name):
                default = getattr(self.instance, field_name)
            annotation = annotations[field_name]
            if (
                self.recursive_selector is not None
                and default is not Parameter.empty
                and self.matches_selector(default)
            ):
                # A nested target need not match the specialized outer factory.
                factory_type = Factory.model_from(
                    default, __recursive__=self.recursive_selector
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

        model = create_model(
            name or f"{self.target.__name__}Config",
            __base__=self.factory_type,
            __module__=Factory.__module__,
            **cast(dict[str, Any], fields),
        )
        model.factory_target = self.target
        model.factory_fields = tuple(fields)
        return model

    def replace_annotation(
        self,
        annotation: Any,
        value: Any,
        factory_type: type[Factory[Any]],
    ) -> Any:
        """Replace matching union branches, preserving alternatives and metadata."""
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
        """Select whole defaults, skipping existing factories before predicates."""
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
        """Match non-None values strictly; unrelated schema errors propagate."""
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
