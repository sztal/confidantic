"""Base configuration model."""

import tomllib
from collections.abc import Collection, Mapping
from contextvars import ContextVar
from copy import copy as shallow_copy
from copy import deepcopy as deep_copy
from importlib import import_module
from inspect import get_annotations, signature
from io import StringIO
from types import MappingProxyType, UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    Protocol,
    Self,
    Union,
    cast,
    get_args,
    get_origin,
    overload,
)

from docstring_parser import DocstringParam, DocstringStyle, compose, parse
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    PrivateAttr,
    PydanticUserError,
    SerializationInfo,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core import PydanticCustomError
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings import (
    SettingsConfigDict as PydanticSettingsConfigDict,
)
from pydantic_settings.sources import DefaultSettingsSource
from pydantic_settings.sources.types import (
    ENV_FILE_SENTINEL,
    DotenvType,
    EnvPrefixTarget,
    PathType,
)
from pydantic_settings.sources.utils import InitState, _get_alias_names
from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.pretty import Pretty
from rich.style import Style
from rich.table import Table
from rich.text import Text

from confidantic.utils import (
    get_import_string,
    import_from_string,
    is_runtime_jupyterlike,
)

__all__ = ("BaseConfig", "ClassDefaultsSource", "ConfigModelDict")

_FieldSource = tuple[
    type[PydanticBaseSettingsSource],
    type[BaseSettings],
]
_NestedModelBaselines = dict[str, BaseModel | object]


class _YamlModule(Protocol):
    def safe_dump(self, data: Any, **kwargs: Any) -> str: ...

    def safe_load(self, stream: str | bytes) -> Any: ...


class _TomlModule(Protocol):
    def dumps(self, data: Any) -> str: ...


_FACTORY_DEFAULT = object()
_DEFERRED_MODEL_DEFAULT = object()
_NESTED_MODEL_BASELINES: ContextVar[_NestedModelBaselines | None] = ContextVar(
    "_NESTED_MODEL_BASELINES",
    default=None,
)
_DISABLE_CLI_PARSE_ARGS: ContextVar[bool] = ContextVar(
    "_DISABLE_CLI_PARSE_ARGS",
    default=False,
)


class ConfigModelDict(PydanticSettingsConfigDict, total=False):
    """Configuration options for :class:`BaseConfig`.

    Attributes
    ----------
    docstring_set_attributes_section
        Whether model fields replace an ``@attrs`` marker in the class
        docstring's ``Attributes`` section when a configuration subclass is
        created. ``None`` enables marker replacement by default.
    model_import_string
        Key used for an optional model import string in serialized output.
        Set to ``None`` to disable the marker for a configuration class.
    """

    docstring_set_attributes_section: bool | None
    model_import_string: str | None


class ClassDefaultsSource(PydanticBaseSettingsSource):
    """Load defaults declared directly on one settings class.

    Static defaults become source values so they participate in BaseConfig's
    per-MRO priority and nested merging. Default factories and discriminated
    defaults act as whole-field barriers until Pydantic evaluates them during
    validation.

    Parameters
    ----------
    settings_cls
        Settings class whose defaults are loaded.
    field_names
        Field names to consider. By default, use fields declared directly on
        ``settings_cls``.
    _init_state
        Optional source state shared with other Pydantic Settings sources.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        field_names: Collection[str] | None = None,
        _init_state: InitState | None = None,
    ) -> None:
        super().__init__(settings_cls, _init_state)
        self.defaults: dict[str, Any] = {}
        field_names = (
            get_annotations(settings_cls) if field_names is None else field_names
        )
        for field_name in field_names:
            if field_name not in settings_cls.model_fields:
                continue
            field = settings_cls.model_fields[field_name]
            if field.is_required():
                continue

            aliases, _ = _get_alias_names(field_name, field)
            key = aliases[0] if aliases else field_name
            if field.default_factory is not None or _field_has_discriminator(field):
                self.defaults[key] = _FACTORY_DEFAULT
            else:
                default = field.get_default(call_default_factory=False)
                adapter_config = (
                    ConfigDict(arbitrary_types_allowed=True)
                    if settings_cls.model_config.get("arbitrary_types_allowed")
                    else None
                )
                try:
                    adapter = TypeAdapter(field.annotation, config=adapter_config)
                except PydanticUserError as error:
                    if error.code != "type-adapter-config-unused":
                        raise
                    adapter = TypeAdapter(field.annotation)
                self.defaults[key] = adapter.dump_python(default)

    def __call__(self) -> dict[str, Any]:
        return self.defaults

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False  # pragma: no cover


class BaseConfig(BaseSettings):
    """Resolve configuration sources independently along the class MRO.

    Each class is resolved using Pydantic Settings source ordering, followed by
    defaults declared directly on that class. Remaining values continue through
    Python's C3 MRO. Nested values retain Pydantic Settings deep-merge behavior.
    Partial updates to Pydantic models retain the concrete type and current
    values of the default or lower-priority initialization instance.

    Resolved instances expose each field's source class and the configuration
    class for which that source was constructed through ``model_field_sources``.

    Instances are frozen by default, so model fields cannot be reassigned after
    validation. Use :meth:`copy` or :meth:`deepcopy` to derive a modified copy,
    or :meth:`mutate` to update an instance in place. Set ``frozen=False`` in
    ``model_config`` when a subclass intentionally requires mutable fields.

    Add an ``@attrs`` marker to a NumPy-style ``Attributes`` section to replace
    that marker with the effective model field names and descriptions. Set
    ``docstring_set_attributes_section=False`` in ``model_config`` to disable
    the replacement.
    """

    model_config: ClassVar[ConfigModelDict] = ConfigModelDict(
        frozen=True,
        env_nested_delimiter="__",
        env_ignore_empty=True,
        env_parse_enums=True,
        env_parse_none_str="null",
        nested_model_default_partial_update=True,
        cli_parse_none_str="null",
        cli_avoid_json=True,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        cli_hide_none_type=True,
        cli_show_env_vars=True,
        cli_use_class_docs_for_groups=True,
        use_attribute_docstrings=True,
        docstring_set_attributes_section=None,
        dotenv_filtering="only_existing",
        model_import_string="__model__",
    )

    _model_field_sources: dict[str, _FieldSource] = PrivateAttr(default_factory=dict)

    def __init__(self, **kwargs: Any) -> None:
        if _DISABLE_CLI_PARSE_ARGS.get() or is_runtime_jupyterlike():
            kwargs["_cli_parse_args"] = False

        build_sources = kwargs.pop("_build_sources", None)
        if build_sources is None:
            option_names = signature(self._settings_init_sources).parameters.keys()
            source_options = {
                key: kwargs.pop(key)
                for key in tuple(kwargs)
                if key in option_names and key != "_init_kwargs"
            }
            build_sources = self._settings_init_sources(
                **source_options,
                _init_kwargs=kwargs,
            )

        token = _NESTED_MODEL_BASELINES.set({})
        try:
            super().__init__(_build_sources=build_sources)
        finally:
            _NESTED_MODEL_BASELINES.reset(token)

        sources, _ = build_sources
        resolved_source = next(
            (
                source
                for source in reversed(sources)
                if isinstance(source, _ResolvedSettingsSource)
            ),
            None,
        )
        if resolved_source is not None:
            self._model_field_sources = resolved_source.field_sources.copy()

    def __copy__(self) -> Self:
        """Return a shallow structural copy of this configuration."""
        return super().__copy__()

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        """Return a deep structural copy of this configuration."""
        return super().__deepcopy__(memo)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if (
            cls.model_config.get("docstring_set_attributes_section") is False
            or cls.__doc__ is None
        ):
            return

        parsed = parse(cls.__doc__, style=DocstringStyle.NUMPYDOC)
        attributes = [
            item
            for item in parsed.meta
            if isinstance(item, DocstringParam) and item.args[0] == "attribute"
        ]
        if not any(item.arg_name == "@attrs" for item in attributes):
            return

        parsed.meta = [item for item in parsed.meta if item not in attributes]
        parsed.meta.extend(
            DocstringParam(
                args=["attribute", field_name],
                description=field.description,
                arg_name=field_name,
                type_name=None,
                is_optional=None,
                default=None,
            )
            for field_name, field in cls.model_fields.items()
        )
        cls.__doc__ = compose(
            parsed,
            style=DocstringStyle.NUMPYDOC,
            indent="    ",
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
        """Serialize this configuration as YAML.

        Parameters
        ----------
        indent
            Number of spaces used to indent nested YAML collections.
        include, exclude, context, by_alias, exclude_unset, exclude_defaults
            Options forwarded to :meth:`model_dump`.
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
        try:
            yaml = cast(_YamlModule, import_module("yaml"))
        except ImportError as error:
            raise ImportError(
                "model_dump_yaml() requires PyYAML; install confidantic[yaml]"
            ) from error

        dump_options = {
            "include": include,
            "exclude": exclude,
            "context": context,
            "by_alias": by_alias,
            "exclude_unset": exclude_unset,
            "exclude_defaults": exclude_defaults,
            "exclude_none": exclude_none,
            "exclude_computed_fields": exclude_computed_fields,
            "round_trip": round_trip,
            "warnings": warnings,
            "fallback": fallback,
            "serialize_as_any": serialize_as_any,
            "polymorphic_serialization": polymorphic_serialization,
        }
        yaml_options: dict[str, Any] = {
            "allow_unicode": True,
            "default_flow_style": False,
            "sort_keys": False,
        }
        if indent is not None:
            yaml_options["indent"] = indent
        return yaml.safe_dump(
            self.model_dump(mode="json", **dump_options),
            **yaml_options,
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
        """Serialize this configuration as TOML.

        Parameters
        ----------
        include, exclude, context, by_alias, exclude_unset, exclude_defaults
            Options forwarded to :meth:`model_dump`.
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
        """
        try:
            tomli_w = cast(_TomlModule, import_module("tomli_w"))
        except ImportError as error:
            raise ImportError(
                "model_dump_toml() requires tomli-w; install confidantic[toml]"
            ) from error

        return tomli_w.dumps(
            self.model_dump(
                mode="json",
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
        """Validate a configuration from YAML data.

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
        """
        try:
            yaml = cast(_YamlModule, import_module("yaml"))
        except ImportError as error:
            raise ImportError(
                "model_validate_yaml() requires PyYAML; install confidantic[yaml]"
            ) from error

        return cls.model_validate(
            yaml.safe_load(yaml_data),
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
        """Validate a configuration from TOML data.

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

        Parameters
        ----------
        **kwargs
            Field values to update. Updates are validated as normal model input.

        Returns
        -------
        Self
            A shallow copy of this configuration, with any updates applied.
        """
        copied = shallow_copy(self)
        return copied if not kwargs else copied._copy_with_updates(kwargs)

    def deepcopy(self, **kwargs: Any) -> Self:
        """Return a deep copy, optionally with validated field updates.

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
        return self

    def model_resolve(self) -> Self:
        """Materialize factory fields in a generated resolved model.

        Resolution uses this instance's current validated values and recursively
        materializes factory configs in nested Pydantic models and standard
        containers without mutating the source.

        Returns
        -------
        Self
            Instance of a cached ``<Source>Resolved`` subclass whose declared
            concrete factory config annotations are replaced by target types.
        """
        from confidantic._config.factory import _model_resolve

        return cast(Self, _model_resolve(self))

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
            Read-only field provenance for this instance.
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
    ) -> Table: ...

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
    ) -> Table | str | None:
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
            Whether to enable Rich colors and text styles.

        Returns
        -------
        Table | str | None
            The table for ``"table"``, its rendering for ``"string"``, or
            ``None`` after printing for ``"print"``.

        Raises
        ------
        ValueError
            If ``output`` is not a supported mode.
        """
        table = cls._build_info_table(
            types=True,
            defaults=True,
            header=header,
            describe=describe,
            colors=colors,
        )
        return cls._render_info(table, output=output, colors=colors)

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
    ) -> Table: ...

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
    ) -> Table | str | None:
        """Present the configuration fields and current values as a Rich table.

        The ``Value`` column contains each validated Python value as stored on
        this instance. Values retain their normal representations, including
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
            Whether to enable Rich colors and text styles.
        types
            Whether to include the ``Type`` column.

        Returns
        -------
        Table | str | None
            The table for ``"table"``, its rendering for ``"string"``, or
            ``None`` after printing for ``"print"``.

        Raises
        ------
        ValueError
            If ``output`` is not a supported mode.
        """
        cls = type(self)
        values = {
            field_name: getattr(self, field_name) for field_name in cls.model_fields
        }
        table = cls._build_info_table(
            values=values,
            types=types,
            defaults=False,
            header=header,
            describe=describe,
            colors=colors,
        )
        return cls._render_info(table, output=output, colors=colors)

    @classmethod
    def _build_info_table(
        cls,
        *,
        values: Mapping[str, Any] | None = None,
        types: bool,
        defaults: bool,
        header: bool,
        describe: bool,
        colors: bool,
    ) -> Table:
        null_style = None if colors else Style()
        highlighter = None if colors else NullHighlighter()
        table = Table(
            title=cls.__name__ if header else None,
            header_style="table.header" if colors else null_style,
            border_style=null_style,
            title_style=null_style,
        )
        table.add_column("Option", style="cyan" if colors else None, no_wrap=True)
        if types:
            table.add_column("Type", style="magenta" if colors else None)
        if values is not None:
            table.add_column("Value")
        if defaults:
            table.add_column("Default")
        if describe:
            table.add_column("Description")

        for field_name, field in cls.model_fields.items():
            cells: list[Any] = [Text(field_name)]
            if types:
                annotation = field.annotation
                if annotation is type(None):
                    annotation_name = "None"
                elif get_origin(annotation) is None and isinstance(annotation, type):
                    annotation_name = annotation.__name__
                else:
                    annotation_name = str(annotation).removeprefix("typing.")
                cells.append(Text(annotation_name))
            if values is not None:
                cells.append(
                    Pretty(
                        values[field_name],
                        highlighter=highlighter,
                    )
                )
            if defaults:
                default: Text | Pretty
                if field.is_required():
                    default = Text("required", style="bold red" if colors else "")
                elif field.default_factory is not None:
                    factory_name = getattr(
                        field.default_factory,
                        "__name__",
                        type(field.default_factory).__name__,
                    )
                    default = Text(
                        f"<factory: {factory_name}>",
                        style="dim" if colors else "",
                    )
                else:
                    default = Pretty(
                        field.get_default(call_default_factory=False),
                        highlighter=highlighter,
                    )
                cells.append(default)
            if describe:
                cells.append(Text(field.description or ""))
            table.add_row(*cells)

        return table

    @staticmethod
    def _render_info(
        table: Table,
        *,
        output: Literal["table", "string", "print"],
        colors: bool,
    ) -> Table | str | None:
        if output not in {"table", "string", "print"}:
            raise ValueError(f"Invalid output mode: {output!r}")
        if output == "table":
            return table
        if output == "string":
            buffer = StringIO()
            Console(
                file=buffer,
                color_system="auto" if colors else None,
                force_terminal=colors,
            ).print(table)
            return buffer.getvalue()

        Console(
            color_system="auto" if colors else None,
            force_terminal=colors,
        ).print(table)
        return None

    @classmethod
    def _settings_init_sources(
        cls,
        _case_sensitive: bool | None = None,
        _nested_model_default_partial_update: bool | None = None,
        _env_prefix: str | None = None,
        _env_prefix_target: EnvPrefixTarget | None = None,
        _env_file: DotenvType | None = ENV_FILE_SENTINEL,
        _env_file_encoding: str | None = None,
        _env_ignore_empty: bool | None = None,
        _env_nested_delimiter: str | None = None,
        _env_nested_max_split: int | None = None,
        _env_parse_none_str: str | None = None,
        _env_parse_enums: bool | None = None,
        _cli_prog_name: str | None = None,
        _cli_parse_args: bool | list[str] | tuple[str, ...] | None = None,
        _cli_settings_source: CliSettingsSource[Any] | None = None,
        _cli_parse_none_str: str | None = None,
        _cli_hide_none_type: bool | None = None,
        _cli_avoid_json: bool | None = None,
        _cli_enforce_required: bool | None = None,
        _cli_use_class_docs_for_groups: bool | None = None,
        _cli_show_env_vars: bool | None = None,
        _cli_exit_on_error: bool | None = None,
        _cli_prefix: str | None = None,
        _cli_flag_prefix_char: str | None = None,
        _cli_implicit_flags: bool | Literal["dual", "toggle"] | None = None,
        _cli_ignore_unknown_args: bool | None = None,
        _cli_kebab_case: bool | Literal["all", "no_enums"] | None = None,
        _cli_shortcuts: Mapping[str, str | list[str]] | None = None,
        _secrets_dir: PathType | None = None,
        _init_kwargs: dict[str, Any] | None = None,
    ) -> tuple[tuple[PydanticBaseSettingsSource, ...], dict[str, Any]]:
        local_options = locals()
        source_options: dict[str, Any] = {
            name: local_options[name]
            for name in signature(BaseSettings._settings_init_sources).parameters
            if name in local_options
        }
        levels = [
            level
            for level in cls.__mro__
            if issubclass(level, BaseConfig) and level is not BaseConfig
        ]
        if not levels:
            return super()._settings_init_sources(**source_options)

        resolved_sources: list[PydanticBaseSettingsSource] = []
        init_kwargs = _init_kwargs if _init_kwargs is not None else {}
        init_state = InitState()
        partial_update = False

        for index, level in enumerate(levels):
            source_builder = BaseSettings.__dict__["_settings_init_sources"].__get__(
                None, level
            )
            level_options = source_options | {
                "_cli_parse_args": _cli_parse_args if index == 0 else False,
                "_cli_settings_source": (_cli_settings_source if index == 0 else None),
                "_init_kwargs": init_kwargs,
            }
            level_sources, _ = source_builder(**level_options)
            default_source = next(
                source
                for source in reversed(level_sources)
                if isinstance(source, DefaultSettingsSource)
            )
            if index == 0:
                partial_update = bool(
                    default_source.nested_model_default_partial_update
                )
            init_state = default_source._init_state
            resolved_sources.extend(
                source
                for source in level_sources
                if not isinstance(source, DefaultSettingsSource)
                and (index == 0 or not isinstance(source, CliSettingsSource))
            )

            defaults = ClassDefaultsSource(
                level,
                _init_state=default_source._init_state,
            )
            if defaults.defaults:
                resolved_sources.append(defaults)

        sources = tuple(resolved_sources)
        resolved_source = _ResolvedSettingsSource(
            cls,
            sources,
            _init_state=init_state,
            nested_model_default_partial_update=partial_update,
        )
        return (*sources, resolved_source), init_kwargs

    @classmethod
    def _settings_build_values(
        cls,
        sources: tuple[PydanticBaseSettingsSource, ...],
        init_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        values = super()._settings_build_values(sources, init_kwargs)
        defaults: dict[str, Any] = {}
        seen_defaults: set[str] = set()

        for source in sources:
            if isinstance(source, ClassDefaultsSource):
                for key, value in source.defaults.items():
                    if key in seen_defaults:
                        continue
                    seen_defaults.add(key)
                    if key not in source.current_state:
                        defaults[key] = value

        values = {
            key: value
            for key, value in values.items()
            if key not in defaults or defaults[key] != value
        }

        resolved_source = next(
            (
                source
                for source in reversed(sources)
                if isinstance(source, _ResolvedSettingsSource)
            ),
            None,
        )
        baselines = _NESTED_MODEL_BASELINES.get()
        if (
            resolved_source is None
            or not resolved_source.nested_model_default_partial_update
            or baselines is None
        ):
            return values

        for field_name, field in cls.model_fields.items():
            if _field_has_discriminator(field):
                continue
            aliases, _ = _get_alias_names(field_name, field)
            keys = aliases or (field_name,)
            selected_key = next(
                (candidate for candidate in keys if candidate in values),
                None,
            )
            if selected_key is None or not isinstance(values[selected_key], Mapping):
                continue

            for source in sources:
                if not isinstance(source, InitSettingsSource):
                    continue
                source_key = next(
                    (
                        candidate
                        for candidate in keys
                        if candidate in source.init_kwargs
                    ),
                    None,
                )
                if source_key is None:
                    continue
                baseline = source.init_kwargs[source_key]
                if not isinstance(baseline, BaseModel):
                    continue
                if not any(candidate in source.current_state for candidate in keys):
                    values[selected_key] = baseline
                else:
                    baselines[field_name] = baseline
                break
            else:
                if not field.is_required():
                    if field.default_factory is not None:
                        if _annotation_has_model(field.annotation):
                            baselines[field_name] = _DEFERRED_MODEL_DEFAULT
                    else:
                        baseline = field.get_default(call_default_factory=False)
                        if isinstance(baseline, BaseModel):
                            baselines[field_name] = baseline

        return values

    def _copy_with_updates(self, updates: Mapping[str, Any]) -> Self:
        cls = type(self)
        values = {
            field_name: getattr(self, field_name) for field_name in cls.model_fields
        }
        values.update(self.model_extra or {})
        values.update(updates)
        copied = cls.model_validate(values, by_alias=True, by_name=True)

        updated_fields = {
            field_name
            for field_name, field in cls.model_fields.items()
            if field_name in updates
            or any(alias in updates for alias in _get_alias_names(field_name, field)[0])
        }
        copied._model_field_sources = self._model_field_sources.copy()
        copied._model_field_sources.update(
            dict.fromkeys(updated_fields, (InitSettingsSource, cls))
        )
        object.__setattr__(
            copied,
            "__pydantic_fields_set__",
            self.model_fields_set | updated_fields,
        )
        return copied

    @model_validator(mode="wrap")
    @classmethod
    def _validate_model_import_string(cls, value: Any, handler: Any) -> Any:
        return cls._resolve_model_import_string(value, handler)

    @classmethod
    def _resolve_model_import_string(cls, value: Any, handler: Any) -> Any:
        marker_key = cls.model_config.get("model_import_string")
        if (
            marker_key is None
            or not isinstance(value, Mapping)
            or marker_key not in value
        ):
            return handler(value)

        marker = value[marker_key]
        if not isinstance(marker, str):
            raise PydanticCustomError(
                "model_import_invalid",
                "Model import string must be a string",
            )
        try:
            model_type = import_from_string(marker, type_hint=type[BaseConfig])
        except ValueError as error:
            raise PydanticCustomError(
                "model_import_invalid",
                "Invalid model import string: {marker}",
                {"marker": marker},
            ) from error
        if not issubclass(model_type, cls):
            raise PydanticCustomError(
                "model_import_type_mismatch",
                "Model import {marker} is not a subclass of {expected}",
                {"marker": marker, "expected": get_import_string(cls)},
            )

        data = {key: item for key, item in value.items() if key != marker_key}
        return model_type.model_validate(data, by_alias=True, by_name=True)

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
        return {"@call": get_import_string(self), **data}

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def _apply_nested_model_partial_update(
        cls,
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        baselines = _NESTED_MODEL_BASELINES.get()
        if baselines is None or info.field_name not in baselines:
            return value

        baseline = baselines[info.field_name]
        if baseline is _DEFERRED_MODEL_DEFAULT:
            baseline = cls.model_fields[info.field_name].get_default(
                call_default_factory=True,
                validated_data=info.data,
            )
        if isinstance(baseline, BaseModel) and isinstance(value, Mapping):
            return _update_nested_model(baseline, value)
        return value


class _ResolvedSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        sources: tuple[PydanticBaseSettingsSource, ...],
        _init_state: InitState,
        nested_model_default_partial_update: bool,
    ) -> None:
        super().__init__(settings_cls, _init_state)
        self.sources = sources
        self.nested_model_default_partial_update = nested_model_default_partial_update
        self.field_sources: dict[str, _FieldSource] = {}

    def __call__(self) -> dict[str, Any]:
        self.field_sources.clear()
        if not all(
            isinstance(source, PydanticBaseSettingsSource) for source in self.sources
        ):
            return {}

        for field_name, field in self.settings_cls.model_fields.items():
            aliases, _ = _get_alias_names(field_name, field)
            keys = aliases or (field_name,)

            for index, source in enumerate(self.sources):
                next_state = (
                    self.sources[index + 1].current_state
                    if index + 1 < len(self.sources)
                    else self.current_state
                )
                if any(
                    key not in source.current_state and key in next_state
                    for key in keys
                ):
                    self.field_sources[field_name] = (
                        type(source),
                        source.settings_cls,
                    )
                    break

        return {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False  # pragma: no cover


def _field_has_discriminator(field: FieldInfo) -> bool:
    return field.discriminator is not None or any(
        isinstance(metadata, Discriminator) for metadata in field.metadata
    )


def _annotation_has_model(annotation: Any) -> bool:
    if isinstance(annotation, type):
        return issubclass(annotation, BaseModel)
    origin = get_origin(annotation)
    if origin is Annotated:
        return _annotation_has_model(get_args(annotation)[0])
    if origin in (Union, UnionType):
        return any(_annotation_has_model(item) for item in get_args(annotation))
    return False


def _update_nested_model(
    model: BaseModel,
    update: Mapping[str, Any],
) -> BaseModel:
    model_type = type(model)
    values = {
        field_name: getattr(model, field_name) for field_name in model_type.model_fields
    }
    remaining = dict(update)
    updated_fields: set[str] = set()

    for field_name, field in model_type.model_fields.items():
        aliases, _ = _get_alias_names(
            field_name,
            field,
            populate_by_name=True,
        )
        key = next((alias for alias in aliases if alias in update), None)
        if key is None:
            continue

        value = update[key]
        current = values[field_name]
        if (
            isinstance(current, BaseModel)
            and isinstance(value, Mapping)
            and not _field_has_discriminator(field)
        ):
            value = _update_nested_model(current, value)
        values[field_name] = value
        updated_fields.add(field_name)
        for alias in aliases:
            remaining.pop(alias, None)

    values.update(model.model_extra or {})
    values.update(remaining)
    updated = model_type.model_validate(values, by_alias=True, by_name=True)
    object.__setattr__(
        updated,
        "__pydantic_fields_set__",
        model.model_fields_set | updated_fields,
    )
    return updated
