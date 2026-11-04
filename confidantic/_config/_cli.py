"""CLI source selection and context-local suppression during resolution."""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from inspect import signature
from types import GenericAlias
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, CliSettingsSource, EnvSettingsSource

# Resolution may construct arbitrary settings inside a target constructor, so
# suppression must reach those calls without changing their public signatures.
_CLI_SUPPRESSED: ContextVar[bool] = ContextVar(
    "confidantic_cli_suppressed", default=False
)


class _FactoryCliSettingsSource(CliSettingsSource[Any]):
    """Expose nested CLI fields from concrete Factory instance defaults."""

    @staticmethod
    def supports(model: type[BaseModel]) -> bool:
        from confidantic._config.factory import Factory

        return any(
            isinstance(field.annotation, type)
            and issubclass(field.annotation, Factory)
            and isinstance(field.default, Factory)
            for field in model.model_fields.values()
        )

    @staticmethod
    def _import_annotation(target: type[Any]) -> Any:
        from confidantic.annotations import Import

        return Import[GenericAlias(type, target)]  # type: ignore[misc]

    def _sort_arg_fields(self, model: type[BaseModel]) -> list[tuple[str, FieldInfo]]:
        from confidantic._config.factory import Factory

        fields = super()._sort_arg_fields(model)
        normalized: list[tuple[str, FieldInfo]] = []
        for field_name, field_info in fields:
            if (
                isinstance(field_info.annotation, type)
                and issubclass(field_info.annotation, Factory)
                and isinstance(field_info.default, Factory)
            ):
                field_info = copy(field_info)
                field_info.annotation = type(field_info.default)
            normalized.append((field_name, field_info))
        return normalized


class _FactoryCliHelpDisabledSettingsSource(_FactoryCliSettingsSource):
    """Keep nested Factory options while omitting the generated help option."""

    def _add_default_help(self) -> None:
        pass


class _CliHelpDisabledSettingsSource(CliSettingsSource[Any]):
    """Omit the generated help option without changing argument parsing."""

    def _add_default_help(self) -> None:
        pass


class _CliSettings:
    """Prepare CLI and environment options for one class in the settings MRO.

    The original env_prefix is retained separately from the normalized
    environment options: None disables that class's ordinary environment source.
    The source method preserves supplied parsers and returns None when upstream
    should construct its normal parser. Suppression is a separate context-local
    policy shared by all settings created during recursive resolution.
    """

    def __init__(
        self,
        model_type: type[BaseSettings],
        options: Mapping[str, Any],
        model_config: Mapping[str, Any],
    ) -> None:
        self.model_type = model_type
        self.help_enabled = model_config.get("cli_help", True)
        self.cli_options: dict[str, Any] = {}
        self.env_options: dict[str, Any] = {}
        for source_type, target in (
            (CliSettingsSource, self.cli_options),
            (EnvSettingsSource, self.env_options),
        ):
            for name in signature(source_type).parameters:
                if f"_{name}" in options:
                    value = options[f"_{name}"]
                    target[name] = (
                        value if value is not None else model_config.get(name)
                    )
        self.env_prefix: str | None = self.env_options["env_prefix"]
        self.env_options["env_prefix"] = self.env_prefix or ""
        if self.env_options["env_parse_none_str"] is not None:
            self.cli_options["cli_parse_none_str"] = self.env_options[
                "env_parse_none_str"
            ]

    def source(
        self, supplied: CliSettingsSource[Any] | None
    ) -> CliSettingsSource[Any] | None:
        """Return a supplied/custom source, or defer normal construction upstream."""
        parse_args = self.cli_options["cli_parse_args"]
        if supplied is not None or parse_args is None or parse_args is False:
            return supplied
        has_factory_fields = _FactoryCliSettingsSource.supports(self.model_type)
        if not has_factory_fields and self.help_enabled:
            return None
        source_type = (
            _FactoryCliSettingsSource
            if self.help_enabled
            else (
                _FactoryCliHelpDisabledSettingsSource
                if has_factory_fields
                else _CliHelpDisabledSettingsSource
            )
        )
        return source_type(
            self.model_type,
            **self.cli_options,
            _env_settings_source=EnvSettingsSource(self.model_type, **self.env_options),
        )

    @staticmethod
    def is_suppressed() -> bool:
        """Whether the current resolution scope disables automatic CLI parsing."""
        return _CLI_SUPPRESSED.get()

    @staticmethod
    @contextmanager
    def suppress() -> Generator[None]:
        """Disable CLI parsing for this scope and restore the enclosing policy."""
        token = _CLI_SUPPRESSED.set(True)
        try:
            yield
        finally:
            _CLI_SUPPRESSED.reset(token)
