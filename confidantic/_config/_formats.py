"""Optional format codecs for JSON-mode configuration values.

Dependencies are loaded before dumping model values, so an unavailable codec
does not run user serializers. Validation remains the caller's responsibility.
"""

from importlib import import_module
from typing import Any, Protocol, cast

from pydantic import BaseModel


class _YamlModule(Protocol):
    """The safe YAML operations used by configuration serialization."""

    def safe_dump(self, data: Any, **kwargs: Any) -> str: ...

    def safe_load(self, stream: str | bytes) -> Any: ...


class _TomlModule(Protocol):
    """The TOML writer operation used by configuration serialization."""

    def dumps(self, data: Any) -> str: ...


def dump_yaml(model: BaseModel, *, indent: int | None, **dump_options: Any) -> str:
    """Dump JSON-mode model values as ordered, block-style YAML.

    Parameters
    ----------
    model
        Model serialized after the optional YAML dependency is loaded.
    indent
        Indentation passed to safe_dump, or None for the writer's default.
    **dump_options
        Options forwarded to model_dump with JSON mode fixed by this helper.

    Raises
    ------
    ImportError
        If PyYAML is absent. Serializer and writer errors propagate unchanged.
    """
    try:
        yaml = cast(_YamlModule, import_module("yaml"))
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        raise ImportError(
            "model_dump_yaml() requires PyYAML; install confidantic[yaml]"
        ) from error

    yaml_options: dict[str, Any] = {
        "allow_unicode": True,
        "default_flow_style": False,
        "sort_keys": False,
    }
    if indent is not None:
        yaml_options["indent"] = indent
    return yaml.safe_dump(model.model_dump(mode="json", **dump_options), **yaml_options)


def load_yaml(data: str | bytes) -> Any:
    """Parse YAML with safe_load, leaving model validation to the caller.

    The result may be a mapping, sequence, scalar, or None for an empty document.
    Missing PyYAML raises ImportError naming the extra; YAML parse errors
    propagate unchanged. Call directives are not evaluated here.
    """
    try:
        yaml = cast(_YamlModule, import_module("yaml"))
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        raise ImportError(
            "model_validate_yaml() requires PyYAML; install confidantic[yaml]"
        ) from error
    return yaml.safe_load(data)


def dump_toml(model: BaseModel, **dump_options: Any) -> str:
    """Dump JSON-mode model values as TOML without altering unsupported values.

    Parameters
    ----------
    model
        Model serialized after the optional TOML writer is loaded.
    **dump_options
        Options forwarded to model_dump with JSON mode fixed by this helper.
        Filtering None-valued fields does not remove None inside containers.

    Raises
    ------
    ImportError
        If tomli-w is absent.
    TypeError
        If the writer cannot represent a dumped value, including None. Model
        serialization errors also propagate unchanged.
    """
    try:
        tomli_w = cast(_TomlModule, import_module("tomli_w"))
    except ModuleNotFoundError as error:
        if error.name != "tomli_w":
            raise
        raise ImportError(
            "model_dump_toml() requires tomli-w; install confidantic[toml]"
        ) from error
    return tomli_w.dumps(model.model_dump(mode="json", **dump_options))
