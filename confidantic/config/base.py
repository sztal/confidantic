"""Base configuration model."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from inspect import get_annotations, signature
from types import MappingProxyType
from typing import Any, Literal

from pydantic import PrivateAttr, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources import DefaultSettingsSource
from pydantic_settings.sources.types import (
    ENV_FILE_SENTINEL,
    DotenvType,
    EnvPrefixTarget,
    PathType,
)
from pydantic_settings.sources.utils import InitState, _get_alias_names

from confidantic.utils import is_runtime_jupyterlike

__all__ = ("BaseConfig", "ClassDefaultsSource")

_FACTORY_DEFAULT = object()

_FieldSource = tuple[
    type[PydanticBaseSettingsSource],
    type[BaseSettings],
]


class ClassDefaultsSource(PydanticBaseSettingsSource):
    """Load defaults declared directly on one settings class.

    Static defaults become source values so they participate in BaseConfig's
    per-MRO priority and nested merging. Default factories remain lazy and act
    as whole-field barriers until Pydantic evaluates them during validation.

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
            if field.default_factory is not None:
                self.defaults[key] = _FACTORY_DEFAULT
            else:
                default = field.get_default(call_default_factory=False)
                self.defaults[key] = TypeAdapter(field.annotation).dump_python(default)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False  # pragma: no cover

    def __call__(self) -> dict[str, Any]:
        return self.defaults


class _ResolvedSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        sources: tuple[PydanticBaseSettingsSource, ...],
        _init_state: InitState,
    ) -> None:
        super().__init__(settings_cls, _init_state)
        self.sources = sources
        self.field_sources: dict[str, _FieldSource] = {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False  # pragma: no cover

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


class BaseConfig(BaseSettings):
    """Resolve configuration sources independently along the class MRO.

    Each class is resolved using Pydantic Settings source ordering, followed by
    defaults declared directly on that class. Remaining values continue through
    Python's C3 MRO. Nested values retain Pydantic Settings deep-merge behavior.

    Resolved instances expose each field's source class and the configuration
    class for which that source was constructed through ``model_field_sources``.
    """

    model_config = SettingsConfigDict(
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
        cli_use_class_docs_for_group=True,
        use_attribute_docstrings=True,
        dotenv_filtering="match_prefix",
    )

    _model_field_sources: dict[str, _FieldSource] = PrivateAttr(default_factory=dict)

    def __init__(self, **kwargs: Any) -> None:
        if is_runtime_jupyterlike():
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

        super().__init__(_build_sources=build_sources)

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

        return {
            key: value
            for key, value in values.items()
            if key not in defaults or defaults[key] != value
        }
