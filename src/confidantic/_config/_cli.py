"""CLI source selection and context-local suppression during resolution."""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from inspect import signature
from types import GenericAlias
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic._internal._utils import is_model_class
from pydantic.dataclasses import is_pydantic_dataclass
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    EnvSettingsSource,
    ForceDecode,
    NoDecode,
)
from pydantic_settings.sources.utils import (
    _annotation_is_complex,
    _get_model_fields,
    _resolve_type_alias,
)
from typing_inspection import typing_objects
from typing_inspection.introspection import is_union_origin

# Resolution may construct arbitrary settings inside a target constructor, so
# suppression must reach those calls without changing their public signatures.
_CLI_SUPPRESSED: ContextVar[bool] = ContextVar(
    "confidantic_cli_suppressed", default=False
)


def _branch_has_nodecode(annotation: Any) -> bool:
    annotation = _resolve_type_alias(annotation)
    origin = get_origin(annotation)
    if typing_objects.is_annotated(origin):
        inner, *meta = get_args(annotation)
        if ForceDecode in meta:
            return False
        if NoDecode in meta:
            return True
        return _branch_has_nodecode(inner)
    if is_union_origin(origin):
        return _union_needs_nodecode(get_args(annotation))
    return False


def _union_needs_nodecode(args: tuple[Any, ...]) -> bool:
    has_nodecode_branch = False
    for arg in args:
        if _branch_has_nodecode(arg):
            has_nodecode_branch = True
            continue
        resolved = _resolve_type_alias(arg)
        origin = get_origin(resolved)
        if is_union_origin(origin):
            if not _union_needs_nodecode(get_args(resolved)):
                return False
        elif _annotation_is_complex(arg, []):
            return False
    return has_nodecode_branch


def needs_union_no_decode(field_info: FieldInfo | None) -> bool:
    """Return whether a union field should inherit ``NoDecode`` from its branches."""
    if field_info is None or not getattr(field_info, "_complete", True):
        return False
    metadata = field_info.metadata
    if NoDecode in metadata or ForceDecode in metadata:
        return False
    annotation = _resolve_type_alias(field_info.annotation)
    origin = get_origin(annotation)
    while typing_objects.is_annotated(origin):
        annotation, *extra = get_args(annotation)
        if NoDecode in extra or ForceDecode in extra:
            return False
        annotation = _resolve_type_alias(annotation)
        origin = get_origin(annotation)
    return is_union_origin(origin) and _union_needs_nodecode(get_args(annotation))


def _collect_nested_models(annotation: Any) -> list[type[Any]]:
    resolved = _resolve_type_alias(annotation)
    origin = get_origin(resolved)
    if typing_objects.is_annotated(origin):
        return _collect_nested_models(get_args(resolved)[0])
    if is_model_class(resolved) or is_pydantic_dataclass(resolved):
        return [resolved]
    if is_union_origin(origin):
        models: list[type[Any]] = []
        for arg in get_args(resolved):
            models.extend(_collect_nested_models(arg))
        return models
    return []


def _has_nested_union_no_decode(
    model: type[Any], visited: set[type[Any]] | None = None
) -> bool:
    if visited is None:
        visited = set()
    if model in visited:
        return False
    visited.add(model)
    for field_info in _get_model_fields(model).values():
        if needs_union_no_decode(field_info):
            return True
        for sub_model in _collect_nested_models(field_info.annotation):
            if _has_nested_union_no_decode(sub_model, visited):
                return True
    return False


class _ConfidanticCliSettingsSource(CliSettingsSource[Any]):
    """Marker base for Confidantic-generated CLI sources normalized in provenance."""


class _FactoryCliSettingsSource(_ConfidanticCliSettingsSource):
    """Expose nested CLI fields from concrete Factory defaults and union NoDecode.

    Parser-facing FieldInfo copies use the default's concrete factory type or
    propagated NoDecode metadata. The original model's annotations and field
    metadata remain unchanged.
    """

    @staticmethod
    def supports(model: type[BaseModel]) -> bool:
        """Detect direct factory-annotated fields with concrete factory defaults.

        Union members and default factories are not evaluated. This check
        decides whether the root parser needs factory-specific field handling.
        """
        from confidantic._config.factory import Factory

        return any(
            isinstance(field.annotation, type)
            and issubclass(field.annotation, Factory)
            and isinstance(field.default, Factory)
            for field in model.model_fields.values()
        )

    @staticmethod
    def _import_annotation(target: type[Any]) -> Any:
        """Represent CLI type choices as import strings constrained to the target."""
        from confidantic.annotations import Import

        return Import[GenericAlias(type, target)]  # type: ignore[misc]

    def decode_complex_value(
        self, field_name: str, field: FieldInfo, value: Any
    ) -> Any:
        """Skip JSON decoding for nested union fields whose complex branches use NoDecode."""
        if needs_union_no_decode(field):
            return value
        return super().decode_complex_value(field_name, field, value)

    def _sort_arg_fields(self, model: type[BaseModel]) -> list[tuple[str, FieldInfo]]:
        """Retain upstream field order while normalizing factory and union-NoDecode fields."""
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
            elif needs_union_no_decode(field_info):
                field_info = copy(field_info)
                field_info.metadata = [*field_info.metadata, NoDecode]
            normalized.append((field_name, field_info))
        return normalized


class _FactoryCliHelpDisabledSettingsSource(_FactoryCliSettingsSource):
    """Keep nested Factory options while omitting the generated help option."""

    def _add_default_help(self) -> None:
        pass


class _CliHelpDisabledSettingsSource(_ConfidanticCliSettingsSource):
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

    Parameters
    ----------
    model_type
        Settings class whose parser and environment policy are being prepared.
    options
        Bound upstream source-builder arguments, including defaults. Non-None
        per-call options override the corresponding model configuration values.
    model_config
        Effective configuration at this MRO level, including custom overrides.

    Attributes
    ----------
    cli_options, env_options
        Resolved keyword arguments supported by the installed source classes.
        A configured environment null token also becomes the CLI null token.
    env_prefix
        Prefix before normalization; ``None`` disables the ordinary environment
        source even though the parser-facing environment options use ``""``.
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
        """Return a supplied/custom source, or defer normal construction upstream.

        Parameters
        ----------
        supplied
            Caller-provided source, returned unchanged without replacing its
            parser or help policy.

        Returns
        -------
        CliSettingsSource | None
            Supplied source or a generated source for factory defaults or
            disabled help. ``None`` leaves ordinary construction to upstream,
            including when automatic parsing is disabled.
        """
        parse_args = self.cli_options["cli_parse_args"]
        if supplied is not None or parse_args is None or parse_args is False:
            return supplied
        needs_normalization = _FactoryCliSettingsSource.supports(
            self.model_type
        ) or _has_nested_union_no_decode(self.model_type)
        if not needs_normalization and self.help_enabled:
            return None
        source_type = (
            _FactoryCliSettingsSource
            if self.help_enabled
            else (
                _FactoryCliHelpDisabledSettingsSource
                if needs_normalization
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
