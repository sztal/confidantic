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
    """Dump JSON-mode model values as ordered, block-style YAML."""
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
    """Parse YAML safely, leaving model validation to the caller."""
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
    """Dump JSON-mode model values as TOML without altering unsupported values."""
    try:
        tomli_w = cast(_TomlModule, import_module("tomli_w"))
    except ModuleNotFoundError as error:
        if error.name != "tomli_w":
            raise
        raise ImportError(
            "model_dump_toml() requires tomli-w; install confidantic[toml]"
        ) from error
    return tomli_w.dumps(model.model_dump(mode="json", **dump_options))
