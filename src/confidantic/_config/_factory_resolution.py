"""Per-call factory value traversal and resolved model type construction.

Public resolution and construction methods import this module lazily.
Value traversal tracks the active recursion path, while type reconstruction
caches generated classes. These states serve different graph semantics and
must not be shared with the cycle-tolerant factory-detection scan.
"""

from collections.abc import Callable, Mapping
from copy import copy
from functools import reduce
from inspect import Parameter
from operator import or_
from types import UnionType
from typing import Annotated, Any, ForwardRef, get_args, get_origin

from pydantic import BaseModel, create_model

from confidantic._config.factory import (
    Factory,
    _constructor_signature,
    _factory_target,
    _is_factory_type,
)


class _ResolvedModelTypes:
    """Build resolved model types for one value-resolution traversal.

    The cache is keyed by original class identity, not class name. Annotation
    dependencies may be cyclic even when values are acyclic, so affected models
    are created together and rebuilt against a complete forward-reference
    namespace. Original classes and their field metadata are not modified.

    Attributes
    ----------
    models
        Original model classes mapped to generated replacements. Only generated
        types are cached; unchanged classes are returned directly.
    """

    def __init__(self) -> None:
        self.models: dict[type[BaseModel], type[BaseModel]] = {}

    def resolve_model(
        self,
        source: type[BaseModel],
        *,
        force: bool = False,
        name: str | None = None,
    ) -> type[BaseModel]:
        """Return a cached or generated model type with Factory annotations resolved.

        Parameters
        ----------
        source
            Original Pydantic model class.
        force
            Generate a subclass even when its annotations need no changes.
            Value traversal uses this for model instances that are rebuilt.
        name
            Name for the source model's generated subclass. Cached classes keep
            the name chosen when they were first created in this traversal.

        Returns
        -------
        type[BaseModel]
            Generated subclass, or the original class if no changes are needed.

        Notes
        -----
        Schema-generation and model-rebuild errors propagate. The cache belongs
        to one public resolution call and is not rolled back after an error.
        """
        if source in self.models:
            return self.models[source]
        # Discover dependencies before creating any replacement classes.
        nodes = [source]
        dependencies: dict[type[BaseModel], set[type[BaseModel]]] = {}
        changed = {source} if force else set()
        for node in nodes:
            references: set[type[BaseModel]] = set()

            def collect(
                model: type[BaseModel], references: set[type[BaseModel]] = references
            ) -> type[BaseModel]:
                references.add(model)
                if model not in nodes and model not in self.models:
                    nodes.append(model)
                return self.models.get(model, model)

            for field in node.model_fields.values():
                if (
                    self.resolve_annotation(field.annotation, collect)
                    != field.annotation
                ):
                    changed.add(node)
            dependencies[node] = references
        # A changed annotation also changes every model that refers to it.
        while True:
            affected = {node for node, refs in dependencies.items() if refs & changed}
            if affected <= changed:
                break
            changed.update(affected)
        if source not in changed:
            return source

        # Temporary names distinguish classes with identical public names and
        # allow self-references and mutual references to be rebuilt together.
        names = {
            node: f"_ConfidanticResolved_{id(self)}_{index}"
            for index, node in enumerate(nodes)
            if node in changed
        }

        def reference(model: type[BaseModel]) -> Any:
            if model in names:
                return ForwardRef(names[model])
            return self.models.get(model, model)

        for node in nodes:
            if node not in changed:
                continue
            fields: dict[str, Any] = {}
            for field_name, field in node.model_fields.items():
                annotation = self.resolve_annotation(field.annotation, reference)
                if annotation != field.annotation:
                    resolved_field = copy(field)
                    resolved_field.annotation = annotation
                    fields[field_name] = (annotation, resolved_field)
            self.models[node] = create_model(
                name if node is source and name else f"{node.__name__}Resolved",
                __base__=node,
                __module__=node.__module__,
                **fields,
            )
        namespace = {key: self.models[node] for node, key in names.items()}
        for node in names:
            self.models[node].model_rebuild(force=True, _types_namespace=namespace)
        return self.models[source]

    def resolve_annotation(
        self,
        annotation: Any,
        resolve_model: Callable[[type[BaseModel]], Any] | None = None,
    ) -> Any:
        """Replace Factory annotations while preserving container and field metadata.

        Parameters
        ----------
        annotation
            Annotation to rewrite, including nested containers and Annotated types.
        resolve_model
            Model-reference callback for graph collection or forward references.
            The default resolves model types using this object's shared cache.

        Returns
        -------
        Any
            The rewritten annotation, or the original when no replacement is needed.
        """
        if resolve_model is None:
            resolve_model = self.resolve_model
        if isinstance(annotation, type):
            if issubclass(annotation, Factory):
                target = _factory_target(annotation)
                return target if target is not None else annotation
            if issubclass(annotation, BaseModel):
                return resolve_model(annotation)
            return annotation

        origin = get_origin(annotation)
        arguments = get_args(annotation)
        if origin is None or not arguments:
            return annotation

        if origin is Annotated:
            return Annotated[
                self.resolve_annotation(arguments[0], resolve_model), *arguments[1:]
            ]
        resolved_arguments = tuple(
            self.resolve_annotation(argument, resolve_model) for argument in arguments
        )
        if resolved_arguments == arguments:
            return annotation
        copy_with = getattr(annotation, "copy_with", None)
        if copy_with is not None:
            return copy_with(resolved_arguments)
        if origin is UnionType:
            return reduce(or_, resolved_arguments)
        return origin[resolved_arguments]


class _FactoryResolver:
    """Resolve one public call using a shared type cache and active value path.

    Generated model classes are reused within the call. Resolved values are not
    cached: repeated factories invoke their targets separately, and shared
    containers and models are rebuilt at each occurrence. Arbitrary objects are
    returned unchanged. Use a fresh resolver for each public resolution call.

    Attributes
    ----------
    active
        Identities on the current recursion path. Entries are removed on return
        or failure so a repeated value in a sibling branch is not a cycle.
    types
        Model-type cache shared across the traversal, including nested models.
    """

    def __init__(self) -> None:
        self.active: set[int] = set()
        self.types = _ResolvedModelTypes()

    def instance(
        self,
        factory: Factory[Any],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Bind root overrides before traversing inputs and constructing a target."""
        identity = id(factory)
        if identity in self.active:
            raise ValueError("cyclic values cannot be resolved")
        self.active.add(identity)
        try:
            constructor = _constructor_signature(factory.factory_target)
            supplied = constructor.bind_partial(*args, **(kwargs or {}))
            values = {
                name: getattr(factory, name)
                for name in factory.factory_fields
                if name not in supplied.arguments
            }
            values.update(supplied.arguments)
            explicit = tuple(values)
            parameters = list(constructor.parameters.values())
            # Positional defaults are needed only to bridge gaps before a supplied
            # positional-only input or a nonempty variadic positional pack.
            last_positional = -1
            for index, parameter in enumerate(parameters):
                if (
                    parameter.kind is Parameter.POSITIONAL_ONLY
                    and parameter.name in values
                ):
                    last_positional = index
                elif parameter.kind is Parameter.VAR_POSITIONAL and values.get(
                    parameter.name
                ):
                    last_positional = index - 1
            for index, parameter in enumerate(parameters):
                if parameter.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                    continue
                if parameter.name not in values:
                    if parameter.default is Parameter.empty:
                        raise TypeError(
                            f"missing a required argument: {parameter.name!r}"
                        )
                    if index <= last_positional:
                        values[parameter.name] = parameter.default
            bound = constructor.bind_partial()
            bound.arguments.update(values)
            constructor.bind(*bound.args, **bound.kwargs)
            for name in explicit:
                bound.arguments[name] = self.resolve(values[name])
            return factory.factory_target(*bound.args, **bound.kwargs)
        finally:
            self.active.remove(identity)

    def resolve(
        self, value: Any, *, name: str | None = None, as_model: bool = False
    ) -> Any:
        """Resolve factories and rebuild supported models and containers recursively.

        Parameters
        ----------
        value
            Factory instance or class, model, container, or ordinary value.
            Factory classes are instantiated with their defaults first.
        name
            Optional generated class name when value is a model instance.
            Recursive calls choose their own default model names.
        as_model
            Rebuild a root factory instance as a model instead of invoking its
            target. This preserves explicit ``BaseConfig.model_resolve`` calls
            on factories; nested factories still construct their targets.

        Returns
        -------
        Any
            Constructed target, validated model, rebuilt built-in container, or
            unchanged ordinary value. Target constructor results are returned
            directly without another traversal.

        Raises
        ------
        ValueError
            If a value occurs again on the active recursion path.

        Notes
        -----
        Constructor and validation errors propagate. Active identities are
        removed on both success and failure; the type cache lasts for this
        public call. CLI suppression is owned by the public model_resolve
        and instance methods and therefore also covers target constructors.
        """
        is_factory = isinstance(value, Factory) and not as_model
        if not is_factory and _is_factory_type(value):
            value = value()
            is_factory = True
        if is_factory:
            return self.instance(value)
        if not isinstance(value, BaseModel | Mapping | list | tuple | set | frozenset):
            return value

        identity = id(value)
        if identity in self.active:
            msg = "cyclic values cannot be resolved"
            raise ValueError(msg)
        self.active.add(identity)
        try:
            if isinstance(value, BaseModel):
                model_type = type(value)
                resolved_type = self.types.resolve_model(
                    model_type, force=True, name=name
                )
                values = {
                    field_name: self.resolve(getattr(value, field_name))
                    for field_name in model_type.model_fields
                }
                if value.model_extra:
                    values.update(
                        {
                            key: self.resolve(item)
                            for key, item in value.model_extra.items()
                        }
                    )
                return resolved_type.model_validate(values, by_alias=True, by_name=True)
            if isinstance(value, Mapping):
                return {
                    self.resolve(key): self.resolve(item) for key, item in value.items()
                }
            # Preserve normalization to built-ins rather than invoking arbitrary
            # container-subclass constructors.
            if isinstance(value, list):
                return [self.resolve(item) for item in value]
            if isinstance(value, tuple):
                return tuple(self.resolve(item) for item in value)
            if isinstance(value, set):
                return {self.resolve(item) for item in value}
            return frozenset(self.resolve(item) for item in value)
        finally:
            self.active.remove(identity)


def contains_factory(value: Any, seen: set[int] | None = None) -> bool:
    """Detect factories without evaluating defaults or traversing arbitrary objects.

    Parameters
    ----------
    value
        Value to inspect through model fields/extras, mapping keys/values, and
        supported built-in containers.
    seen
        Identities already scanned during this detection pass. A fresh set is
        created when omitted; it is separate from resolution's active path.

    Returns
    -------
    bool
        Whether a Factory instance or class occurs in the traversed structure.
        Cyclic structures without factories return False.
    """
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
            contains_factory(getattr(value, field_name), seen)
            for field_name in type(value).model_fields
        ) or any(
            contains_factory(item, seen) for item in (value.model_extra or {}).values()
        )
    if isinstance(value, Mapping):
        return any(
            contains_factory(key, seen) or contains_factory(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_factory(item, seen) for item in value)
    return False
