"""Public configuration model and Pydantic integration hooks.

Settings assembly, nested updates, CLI control, and optional features have
separate owners. This module keeps the documented interface and dispatches
through subclass hooks so extraction does not change configuration semantics.
"""

import tomllib
from collections.abc import Callable, Mapping
from copy import copy as shallow_copy
from copy import deepcopy as deep_copy
from inspect import signature
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, cast, overload

from dotenv import find_dotenv
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    GetCoreSchemaHandler,
    PrivateAttr,
    SerializationInfo,
    ValidationInfo,
    field_validator,
    model_serializer,
)
from pydantic_core import CoreSchema, PydanticUndefined
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from confidantic._config import _formats
from confidantic._config._cli import _CliSettings
from confidantic._config._docstrings import replace_attributes
from confidantic._config._nested import _NestedModelUpdates
from confidantic._config._options import ConfigModelDict
from confidantic._config._settings import (
    _FieldSource,
    _SettingsSources,
    validate_settings,
    wrap_settings_schema,
)
from confidantic.utils import get_import_string, is_runtime_jupyterlike

if TYPE_CHECKING:
    from rich.table import Table

__all__ = ("BaseConfig",)


class BaseConfig(BaseSettings):
    """Resolve configuration sources independently along the class MRO.

    Configure settings behavior with ``model_config``; see
    :class:`ConfigModelDict` for common Pydantic Settings options and
    Confidantic extensions. General Pydantic model configuration options
    remain available through :class:`pydantic.ConfigDict`.
    See :class:`pydantic_settings.BaseSettings` to determine which settings
    options can also be configured at initialization with a leading underscore.

    By default, CLI input for the most-derived class has highest priority.
    Each class then contributes initialization, environment, dotenv, and secret
    sources, followed by defaults declared directly on that class, in Python's
    C3 MRO. Source customization can change the ordering within a level. A child
    default can therefore outrank a parent's environment value. Sources are
    evaluated even when higher-priority values already fill all fields; final
    validation uses the most-derived model. Nested mappings are deep-merged.
    Lists and other non-mapping values are replaced rather than concatenated.
    Partial updates to Pydantic models retain the concrete type and current
    values of the default or lower-priority initialization instance when
    ``nested_model_default_partial_update`` is enabled (the default).
    Discriminated fields select a variant rather than patching the baseline.
    Process environment parsing is disabled by default (``env_prefix=None``);
    dotenv loading and CLI parsing are opt-in. Notebook-like runtimes suppress
    automatic CLI parsing.

    Validation of merged settings retains per-call ``strict``, ``extra``, and
    ``context`` options. Custom ``__init__`` methods retain Pydantic's limitations.
    The schema wrapper also retains Pydantic's strict-JSON limitation for inputs
    such as date strings and tuple arrays; strict JSON validation can reject
    those representations. Partial updates to existing nested models validate
    separately and do not yet forward per-call options to that nested pass.

    Resolved instances expose each field's source class and the configuration
    class for which that source was constructed through ``model_field_sources``.

    Instances are frozen by default, so model fields cannot be reassigned after
    validation. Use :meth:`copy` or :meth:`deepcopy` to derive a modified copy,
    or :meth:`mutate` to update an instance in place. Set ``frozen=False`` in
    ``model_config`` when a subclass intentionally requires mutable fields.

    Add an ``@attrs`` marker to a NumPy or Google ``Attributes`` section to
    replace the section with effective model field names and descriptions.
    Google sections also accept ``@attrs:``. The format is detected unless
    ``docstring_style`` specifies ``"numpy"`` or ``"google"``. Set
    ``docstring_set_attributes_section=False`` in ``model_config`` to disable
    the replacement. Generation requires ``confidantic[docstrings]``;
    ordinary field-description extraction does not require that extra.
    """

    model_config: ClassVar[ConfigModelDict] = ConfigModelDict(
        frozen=True,
        validate_default=True,
        env_prefix=cast(Any, None),
        env_nested_delimiter="__",
        env_ignore_empty=True,
        env_parse_enums=True,
        env_parse_none_str="null",
        nested_model_default_partial_update=True,
        cli_parse_none_str="null",
        cli_avoid_json=True,
        cli_implicit_flags=False,
        cli_kebab_case=True,
        cli_hide_none_type=True,
        cli_show_env_vars=True,
        cli_use_class_docs_for_groups=True,
        cli_ignore_unknown_args=True,
        cli_help=True,
        use_attribute_docstrings=not is_runtime_jupyterlike(),
        docstring_set_attributes_section=None,
        docstring_style=None,
        dotenv_filtering="only_existing",
        env_file_discovery=False,
    )

    _model_field_sources: dict[str, _FieldSource] = PrivateAttr(default_factory=dict)
    _model_init_fields: set[str] = PrivateAttr(default_factory=set)

    # Retain Pydantic's native initialization path, so model_validate and
    # TypeAdapter keep their active strict/extra/context options.
    __init__ = cast(Any, BaseModel.__init__)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return wrap_settings_schema(source_type, handler)

    @classmethod
    def _validate_settings(cls, value: Any, handler: Callable[[Any], Any]) -> Any:
        return validate_settings(cls, value, handler)

    def __copy__(self) -> Self:
        """Return a shallow structural copy of this configuration."""
        return super().__copy__()

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        """Return a deep structural copy of this configuration."""
        return super().__deepcopy__(memo)

    @classmethod
    def find_dotenv(cls) -> str:
        """Locate the dotenv file used when automatic discovery is enabled.

        Delegates to ``dotenv.find_dotenv()`` with its default search policy.
        In ordinary script execution, the search starts at this method's source
        directory in Confidantic and walks upward. Interactive or debugger
        execution can instead start at the current working directory. Override
        this method to choose an application-specific search location.

        Returns
        -------
        str
            Path to the discovered dotenv file, or an empty string when none
            is found.
        """
        return find_dotenv()

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Track source customizations and expand explicitly marked docstrings."""
        super().__pydantic_init_subclass__(**kwargs)
        descriptor = next(
            base.__dict__["settings_customise_sources"]
            for base in cls.__mro__
            if "settings_customise_sources" in base.__dict__
        )
        method = (
            descriptor.__func__
            if isinstance(descriptor, (classmethod, staticmethod))
            else descriptor
        )
        if not getattr(method, "_confidantic_tracks_init", False):
            tracked: Any = _SettingsSources.track_customization(method)
            if isinstance(descriptor, (classmethod, staticmethod)):
                tracked = type(descriptor)(tracked)
            cast(Any, cls).settings_customise_sources = tracked
        if (
            cls.model_config.get("docstring_set_attributes_section") is False
            or cls.__doc__ is None
        ):
            return

        cls.__doc__ = replace_attributes(
            cls.__doc__,
            fields={
                name: field.description for name, field in cls.model_fields.items()
            },
            style=cls.model_config.get("docstring_style"),
            class_name=cls.__qualname__,
        )

    def model_dump_yaml(
        self,
        *,
        indent: int | None = None,
        include: Any = None,
        exclude: Any = None,
        context: Any = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_computed_fields: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Any = None,
        serialize_as_any: bool = False,
        polymorphic_serialization: bool | None = None,
    ) -> str:
        """Serialize this configuration as YAML using JSON-mode model values.

        Parameters
        ----------
        indent
            Number of spaces used to indent nested YAML collections.
        include, exclude, by_alias, exclude_unset, exclude_defaults
            Options forwarded to :meth:`model_dump`.
        context
            Serialization context forwarded to :meth:`model_dump`. Pass
            ``{"make": True}`` to add an ``@call`` directive containing the
            configuration class's identifier, or a Factory's target identifier.
            Load directives through a Make annotation; :meth:`model_validate_yaml`
            and :meth:`model_validate_toml` do not evaluate a root directive.
            Targets must be importable. Factory directives contain only
            ``factory_fields``, using constructor keyword names even when
            aliases are enabled. Ambiguous serialized constructor keys raise
            an error. For other models, use ``serialize_as_any=True`` when
            subclass-only fields must be retained.
        exclude_none, exclude_computed_fields, round_trip, warnings, fallback
            Options forwarded to :meth:`model_dump`.
        serialize_as_any, polymorphic_serialization
            Options forwarded to :meth:`model_dump`.

        Returns
        -------
        str
            Block-style YAML serialization of the configuration.

        Raises
        ------
        ImportError
            If PyYAML is not installed.
        """
        return _formats.dump_yaml(
            self,
            indent=indent,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            exclude_computed_fields=exclude_computed_fields,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
            polymorphic_serialization=polymorphic_serialization,
        )

    def model_dump_toml(
        self,
        *,
        include: Any = None,
        exclude: Any = None,
        context: Any = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_computed_fields: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Any = None,
        serialize_as_any: bool = False,
        polymorphic_serialization: bool | None = None,
    ) -> str:
        """Serialize this configuration as TOML using JSON-mode model values.

        TOML has no null value. ``exclude_none=True`` omits None-valued model
        fields, but None values inside containers still require preprocessing.

        Parameters
        ----------
        include, exclude, by_alias, exclude_unset, exclude_defaults
            Options forwarded to :meth:`model_dump`.
        context
            Serialization context forwarded to :meth:`model_dump`. Pass
            ``{"make": True}`` to add an ``@call`` directive containing the
            configuration class's identifier, or a Factory's target identifier.
            Load directives through a Make annotation; :meth:`model_validate_yaml`
            and :meth:`model_validate_toml` do not evaluate a root directive.
            Targets must be importable. Factory directives contain only
            ``factory_fields``, using constructor keyword names even when
            aliases are enabled. Ambiguous serialized constructor keys raise
            an error. For other models, use ``serialize_as_any=True`` when
            subclass-only fields must be retained.
        exclude_none, exclude_computed_fields, round_trip, warnings, fallback
            Options forwarded to :meth:`model_dump`.
        serialize_as_any, polymorphic_serialization
            Options forwarded to :meth:`model_dump`.

        Returns
        -------
        str
            TOML serialization of the configuration.

        Raises
        ------
        ImportError
            If tomli-w is not installed.
        TypeError
            If dumped values cannot be represented in TOML, including ``None``.
        """
        return _formats.dump_toml(
            self,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            exclude_computed_fields=exclude_computed_fields,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
            polymorphic_serialization=polymorphic_serialization,
        )

    @classmethod
    def model_validate_yaml(
        cls,
        yaml_data: str | bytes,
        *,
        strict: bool | None = None,
        extra: Any = None,
        from_attributes: bool | None = None,
        context: Any = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Parse YAML with ``safe_load`` and validate it as Python model input.

        A root ``@call`` entry is not evaluated. Use a Make annotation to load
        documents containing root directives. Normal settings construction can
        still consult configured sources.

        Parameters
        ----------
        yaml_data
            YAML data to parse and validate.
        strict, extra, from_attributes, context, by_alias, by_name
            Options forwarded to :meth:`model_validate`.

        Returns
        -------
        Self
            The validated configuration.

        Raises
        ------
        ImportError
            If PyYAML is not installed.
        yaml.YAMLError
            If the YAML document cannot be parsed by ``safe_load``.
        ValidationError
            If the parsed value or resolved settings fail model validation.

        Notes
        -----
        Per-call options apply to validation of the merged settings. A subclass
        with its own ``__init__`` retains Pydantic's custom-constructor limitations.
        Partial updates to an existing nested model still validate that model
        separately without forwarding these options; disable
        ``nested_model_default_partial_update`` when this distinction matters.
        """
        return cls.model_validate(
            _formats.load_yaml(yaml_data),
            strict=strict,
            extra=extra,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )

    @classmethod
    def model_validate_toml(
        cls,
        toml_data: str,
        *,
        strict: bool | None = None,
        extra: Any = None,
        from_attributes: bool | None = None,
        context: Any = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Parse TOML and validate it as Python model input.

        A root ``@call`` entry is not evaluated. Use a Make annotation to load
        documents containing root directives. Normal settings construction can
        still consult configured sources.

        Parameters
        ----------
        toml_data
            TOML data to parse and validate.
        strict, extra, from_attributes, context, by_alias, by_name
            Options forwarded to :meth:`model_validate`.

        Returns
        -------
        Self
            The validated configuration.

        Raises
        ------
        tomllib.TOMLDecodeError
            If the document is not valid TOML.
        ValidationError
            If the parsed value or resolved settings fail model validation.

        Notes
        -----
        Per-call options apply to validation of the merged settings. A subclass
        with its own ``__init__`` retains Pydantic's custom-constructor limitations.
        Partial updates to an existing nested model still validate that model
        separately without forwarding these options; disable
        ``nested_model_default_partial_update`` when this distinction matters.
        """
        return cls.model_validate(
            tomllib.loads(toml_data),
            strict=strict,
            extra=extra,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )

    def copy(self, **kwargs: Any) -> Self:
        """Return a shallow copy, optionally with validated field updates.

        Without updates this is a structural copy. With updates, all current
        field and extra values are revalidated as a new instance, so validators
        may rebuild containers and configured settings sources may participate.
        Non-idempotent validators can change fields that were not updated.
        Private attributes are initialized afresh during reconstruction.

        Parameters
        ----------
        **kwargs
            Field values to update. Updates are validated as normal model input.

        Returns
        -------
        Self
            A shallow copy of this configuration, with any updates applied.

        Notes
        -----
        Field names and validation aliases are accepted as updates. Carried-over
        initialization values retain their original provenance and explicit-field
        status. Values supplied by active settings sources receive fresh metadata,
        including when they override requested updates. Accepted extra updates
        participate in ``model_fields_set``; ignored extras do not.

        Examples
        --------
        >>> from pydantic import field_validator
        >>> class Config(BaseConfig):
        ...     count: int = 1
        ...     label: str = "original"
        ...
        ...     @field_validator("count")
        ...     @classmethod
        ...     def double(cls, value: int) -> int:
        ...         return value * 2
        >>> config = Config()
        >>> config.count, config.copy().count
        (2, 2)
        >>> config.copy(label="updated").count
        4
        """
        copied = shallow_copy(self)
        return copied if not kwargs else copied._copy_with_updates(kwargs)

    def deepcopy(self, **kwargs: Any) -> Self:
        """Return a deep copy, optionally with validated field updates.

        Existing state is deep-copied first; supplied updates then follow the
        revalidation behavior of :meth:`copy` and are not themselves deep-copied.
        With updates, reconstruction initializes private attributes afresh and
        uses the same source and metadata rules as :meth:`copy`.

        Parameters
        ----------
        **kwargs
            Field values to update. Updates are validated as normal model input.

        Returns
        -------
        Self
            A deep copy of this configuration, with any updates applied.
        """
        copied = deep_copy(self)
        return copied if not kwargs else copied._copy_with_updates(kwargs)

    def mutate(self, **kwargs: Any) -> Self:
        """Update this configuration in place with validated field values.

        With updates, all current fields and extras undergo the reconstruction
        described by :meth:`copy`, including settings-source participation and
        its metadata rules. The resulting fields, extras, and metadata
        replace those on this instance; existing private attributes are retained.
        With no updates, return the instance without validation.

        Parameters
        ----------
        **kwargs
            Field values to update. Updates are validated as normal model input.

        Returns
        -------
        Self
            This configuration after the updates are applied.

        Raises
        ------
        ValidationError
            If any update fails validation.

        Notes
        -----
        Use this carefully on frozen configurations. Changing their fields may
        invalidate their hashes, so they must not remain dictionary keys or set
        members after mutation.
        """
        if not kwargs:
            return self

        updated = self._copy_with_updates(kwargs)
        for field_name in type(self).model_fields:
            object.__setattr__(self, field_name, getattr(updated, field_name))
        object.__setattr__(self, "__pydantic_extra__", updated.__pydantic_extra__)
        object.__setattr__(
            self,
            "__pydantic_fields_set__",
            updated.__pydantic_fields_set__,
        )
        self._model_field_sources.clear()
        self._model_field_sources.update(updated._model_field_sources)
        self._model_init_fields = updated._model_init_fields.copy()
        return self

    def model_resolve(
        self,
        *,
        name: str | None = None,
    ) -> Self:
        """Recursively resolve nested Factory values in a generated model copy.

        Traversal includes Pydantic model fields and extras, mapping keys and
        values, lists, tuples, sets, and frozensets. Factory classes are first
        instantiated with their defaults. Factory annotations are replaced with
        target types, and rebuilt model instances undergo validation. Mappings
        become dictionaries; arbitrary object attributes are not traversed.
        CLI parsing is disabled during resolution, but other settings sources
        remain active.

        Parameters
        ----------
        name
            Optional name for the generated resolved model class. The default
            appends ``Resolved`` to this model's class name.

        Returns
        -------
        Self
            A resolved model instance. When no Factory value exists anywhere
            in the traversed values, this is a shallow copy of the current
            instance and ``name`` is ignored.

        Raises
        ------
        ValueError
            If resolution traverses a cycle. Nested validation and target
            constructor errors also propagate.

        Notes
        -----
        Resolution rebuilds traversed containers and Pydantic models but does
        not deep-copy arbitrary objects. Shared factories are resolved separately
        at each occurrence. Rebuilt models initialize private state and source
        metadata anew. Self-referential and mutually recursive model annotations
        are supported for acyclic values. Generated types are shared within one
        resolution call; original model types are not modified.
        """
        from confidantic._config.factory import (
            _contains_factory,
            _resolve_model_instance,
        )

        if not _contains_factory(self):
            return shallow_copy(self)
        with _CliSettings.suppress():
            return cast(
                Self,
                _resolve_model_instance(
                    self,
                    set(),
                    name=name,
                ),
            )

    @property
    def model_field_sources(self) -> Mapping[str, _FieldSource]:
        """Map field names to their resolution and inheritance coordinates.

        Each value contains the settings source class followed by the actual
        configuration class for which that source was constructed. Keys are
        canonical model field names rather than aliases.

        For a field assembled by nested merging, the coordinate identifies the
        highest-priority source that established the top-level field. Validators
        retain their input source, while default factories are attributed to
        :class:`ClassDefaultsSource`.

        Returns
        -------
        Mapping[str, tuple[type[PydanticBaseSettingsSource], type[BaseSettings]]]
            Read-only view of field provenance for this instance. If any
            configured source is a bare callable rather than a settings-source
            instance, automatic provenance tracking returns an empty mapping.
            Extras and computed fields are not tracked. Validated updates use
            the metadata rules described in :meth:`copy`.
        """
        return MappingProxyType(self._model_field_sources)

    @classmethod
    @overload
    def model_info(
        cls,
        output: Literal["print"] = "print",
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
    ) -> None: ...

    @classmethod
    @overload
    def model_info(
        cls,
        output: Literal["table"],
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
    ) -> "Table": ...

    @classmethod
    @overload
    def model_info(
        cls,
        output: Literal["string"],
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
    ) -> str: ...

    @classmethod
    def model_info(
        cls,
        output: Literal["table", "string", "print"] = "print",
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
    ) -> "Table | str | None":
        """Present the configuration options as a Rich table.

        Options use canonical model field names and retain Pydantic's field
        order. Required fields are identified in the ``Default`` column, while
        default factories are named without being evaluated.

        Parameters
        ----------
        output
            Output mode. ``"table"`` returns the Rich table, ``"string"``
            returns a rendering, and ``"print"`` prints the table.
        header
            Whether to display the configuration class name above the table.
        describe
            Whether to include the ``Description`` column.
        colors
            Whether to enable Rich colors and text styles. For printed and
            string output, ``True`` forces terminal rendering, including ANSI
            escapes when supported. Rich still honors environment controls such
            as ``NO_COLOR`` and ``TERM``. A returned table is styled but its
            eventual rendering is controlled by the caller's console.

        Returns
        -------
        Table | str | None
            The table for ``"table"``, its rendering for ``"string"``, or
            ``None`` after printing for ``"print"``.

        Raises
        ------
        ImportError
            If Rich is not installed; install ``confidantic[rich]``.
        ValueError
            If ``output`` is not a supported mode.

        Notes
        -----
        Rich return types are imported only for static type checking. Runtime
        evaluation of these annotations requires a namespace containing Table.
        """
        try:
            from confidantic._config._info import _InfoRenderer
        except ModuleNotFoundError as error:
            if error.name != "rich":
                raise
            raise ImportError(
                "model_info() requires Rich; install confidantic[rich]"
            ) from error

        renderer = _InfoRenderer(cls, header=header, describe=describe, colors=colors)
        table = renderer.build_table(types=True, defaults=True)
        return renderer.render(table, output=output)

    @overload
    def info(
        self,
        output: Literal["print"] = "print",
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
        types: bool = False,
    ) -> None: ...

    @overload
    def info(
        self,
        output: Literal["table"],
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
        types: bool = False,
    ) -> "Table": ...

    @overload
    def info(
        self,
        output: Literal["string"],
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
        types: bool = False,
    ) -> str: ...

    def info(
        self,
        output: Literal["table", "string", "print"] = "print",
        header: bool = True,
        describe: bool = True,
        colors: bool = False,
        types: bool = False,
    ) -> "Table | str | None":
        """Present the configuration fields and current values as a Rich table.

        The ``Value`` column contains each validated Python value as stored on
        this instance. Extra fields and source provenance are not displayed.
        Values retain their normal representations, including
        the masked representations of Pydantic secret types.

        Parameters
        ----------
        output
            Output mode. ``"table"`` returns the Rich table, ``"string"``
            returns a rendering, and ``"print"`` prints the table.
        header
            Whether to display the configuration class name above the table.
        describe
            Whether to include the ``Description`` column.
        colors
            Whether to enable Rich colors and text styles. For printed and
            string output, ``True`` forces terminal rendering, including ANSI
            escapes when supported. Rich still honors environment controls such
            as ``NO_COLOR`` and ``TERM``. A returned table is styled but its
            eventual rendering is controlled by the caller's console.
        types
            Whether to include the ``Type`` column.

        Returns
        -------
        Table | str | None
            The table for ``"table"``, its rendering for ``"string"``, or
            ``None`` after printing for ``"print"``.

        Raises
        ------
        ImportError
            If Rich is not installed; install ``confidantic[rich]``.
        ValueError
            If ``output`` is not a supported mode.

        Notes
        -----
        Rich return types are imported only for static type checking. Runtime
        evaluation of these annotations requires a namespace containing Table.
        """
        try:
            from confidantic._config._info import _InfoRenderer
        except ModuleNotFoundError as error:
            if error.name != "rich":
                raise
            raise ImportError(
                "info() requires Rich; install confidantic[rich]"
            ) from error

        cls = type(self)
        renderer = _InfoRenderer(cls, header=header, describe=describe, colors=colors)
        values = {name: getattr(self, name) for name in cls.model_fields}
        table = renderer.build_table(values=values, types=types, defaults=False)
        return renderer.render(table, output=output)

    @classmethod
    def _settings_init_sources(
        cls,
        *args: Any,
        **upstream_options: Any,
    ) -> tuple[tuple[PydanticBaseSettingsSource, ...], dict[str, Any]]:
        bound_options = signature(BaseSettings._settings_init_sources).bind(
            *args, **upstream_options
        )
        bound_options.apply_defaults()
        levels = tuple(
            level
            for level in cls.__mro__
            if issubclass(level, BaseConfig) and level is not BaseConfig
        )
        return _SettingsSources(
            cls,
            levels=levels,
            options=bound_options.arguments,
            find_dotenv=cls.find_dotenv,
        ).build(super()._settings_init_sources)

    @classmethod
    def _settings_build_values(
        cls,
        sources: tuple[PydanticBaseSettingsSource, ...],
        init_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        values = super()._settings_build_values(sources, init_kwargs)
        return _SettingsSources.finalize_values(cls, sources, values)

    def _copy_with_updates(self, updates: Mapping[str, Any]) -> Self:
        cls = type(self)
        case_sensitive = cls.model_config.get("case_sensitive", False)
        normalized = {
            key if case_sensitive else key.lower(): value
            for key, value in updates.items()
        }
        updated_fields = set()
        for name, field in cls.model_fields.items():
            alias = field.validation_alias
            aliases = alias.choices if isinstance(alias, AliasChoices) else [alias]
            for candidate in [name, *aliases]:
                path = (
                    candidate.path if isinstance(candidate, AliasPath) else [candidate]
                )
                if not isinstance(path[0], str):
                    continue
                root = path[0] if case_sensitive else path[0].lower()
                if (
                    AliasPath(root, *path[1:]).search_dict_for_path(normalized)
                    is not PydanticUndefined
                ):
                    updated_fields.add(name)
                    break
        values = {
            name: getattr(self, name)
            for name in cls.model_fields
            if name not in updated_fields
        }
        values.update(self.model_extra or {})
        values.update(updates)
        copied = cls.model_validate(values, by_alias=True, by_name=True)
        explicit_updates = updated_fields | (
            set(updates) & set(copied.model_extra or {})
        )
        carried_fields = copied._model_init_fields - explicit_updates
        for name in carried_fields:
            previous = self._model_field_sources.get(name)
            if previous is None:
                copied._model_field_sources.pop(name, None)
            else:
                copied._model_field_sources[name] = previous
        object.__setattr__(
            copied,
            "__pydantic_fields_set__",
            self.model_fields_set | (copied.model_fields_set - carried_fields),
        )
        return copied

    @model_serializer(mode="wrap")
    def _serialize_with_make(
        self,
        handler: Any,
        info: SerializationInfo,
    ) -> Any:
        data = handler(self)
        context = info.context
        if not isinstance(context, Mapping) or not context.get("make"):
            return data
        if not isinstance(data, Mapping):  # pragma: no cover
            raise TypeError("Model serialization must produce a mapping")
        if "@call" in data:
            raise ValueError(
                "Make directive key '@call' conflicts with serialized data"
            )
        from confidantic._config.factory import Factory

        if isinstance(self, Factory):
            by_alias = cast(bool | None, info.by_alias)
            if by_alias is None:
                by_alias = self.model_config.get("serialize_by_alias", False)
            owners: dict[str, list[str]] = {}
            for name, field in type(self).model_fields.items():
                key = (field.serialization_alias if by_alias else None) or name
                owners.setdefault(key, []).append(name)
            for name, computed in type(self).model_computed_fields.items():
                key = (computed.alias if by_alias else None) or name
                owners.setdefault(key, []).append(name)
            for name in self.model_extra or {}:
                owners.setdefault(name, []).append(name)
            arguments = {}
            for name in self.factory_fields:
                field = type(self).model_fields[name]
                key = (field.serialization_alias if by_alias else None) or name
                if key in data:
                    if len(owners[key]) != 1:
                        raise ValueError(
                            f"Ambiguous serialized constructor argument: {name}"
                        )
                    arguments[name] = data[key]
            return {"@call": get_import_string(self.factory_target), **arguments}
        return {"@call": get_import_string(self), **data}

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def _apply_nested_model_partial_update(
        cls,
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        updates = _NestedModelUpdates.current()
        return value if updates is None else updates.apply(cls, value, info)
