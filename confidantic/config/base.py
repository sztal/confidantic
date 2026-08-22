"""Base configuration model."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from inspect import get_annotations, signature
from typing import Any, Literal

from pydantic import TypeAdapter
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import DefaultSettingsSource
from pydantic_settings.sources.types import (
    ENV_FILE_SENTINEL,
    DotenvType,
    EnvPrefixTarget,
    PathType,
)
from pydantic_settings.sources.utils import InitState, _get_alias_names

__all__ = ("BaseConfig", "ClassDefaultsSource")

_FACTORY_DEFAULT = object()


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


class BaseConfig(BaseSettings):
    """Resolve configuration sources independently along the class MRO.

    Each class is resolved using Pydantic Settings source ordering, followed by
    defaults declared directly on that class. Remaining values continue through
    Python's C3 MRO. Nested values retain Pydantic Settings deep-merge behavior.
    """

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

        return tuple(resolved_sources), init_kwargs

    @classmethod
    def _settings_build_values(
        cls,
        sources: tuple[PydanticBaseSettingsSource, ...],
        init_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        values = super()._settings_build_values(sources, init_kwargs)
        defaults: dict[str, Any] = {}

        for source in sources:
            if isinstance(source, ClassDefaultsSource):
                for key, value in source.defaults.items():
                    defaults.setdefault(key, value)

        return {
            key: value
            for key, value in values.items()
            if key not in defaults or defaults[key] != value
        }
