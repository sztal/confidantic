"""YAML and TOML serialization and model validation."""

import tomllib
from importlib import import_module
from typing import Any, cast

import pytest
from pydantic import Field

from confidantic import BaseConfig
from tests._config.models import PolymorphicChildConfig, PolymorphicContainer


class FormatConfig(BaseConfig):
    """Configuration used to test YAML and TOML serialization."""

    name: str = "example"
    nested: dict[str, int] = Field(default_factory=lambda: {"value": 1})
    optional: str | None = None


def test_model_dump_yaml_forwards_model_dump_options() -> None:
    """YAML dumps preserve marker ordering and forwarded dump options."""
    yaml = cast(Any, import_module("yaml"))
    config = FormatConfig()

    result = config.model_dump_yaml(
        context={"make": True},
        exclude_none=True,
        indent=4,
    )

    assert result == (
        "'@call': tests._config.test_formats:FormatConfig\n"
        "name: example\n"
        "nested:\n"
        "    value: 1\n"
    )
    assert yaml.safe_load(result) == {
        "@call": "tests._config.test_formats:FormatConfig",
        "name": "example",
        "nested": {"value": 1},
    }


def test_model_dump_toml_forwards_model_dump_options() -> None:
    """TOML dumps preserve marker ordering and forwarded dump options."""
    config = FormatConfig()

    result = config.model_dump_toml(
        context={"make": True},
        exclude_none=True,
    )

    assert result == (
        '"@call" = "tests._config.test_formats:FormatConfig"\n'
        'name = "example"\n\n'
        "[nested]\n"
        "value = 1\n"
    )
    assert tomllib.loads(result) == {
        "@call": "tests._config.test_formats:FormatConfig",
        "name": "example",
        "nested": {"value": 1},
    }


@pytest.mark.parametrize(
    ("method_name", "arguments", "extra"),
    [
        ("model_dump_yaml", (), "yaml"),
        ("model_validate_yaml", ("",), "yaml"),
        ("model_dump_toml", (), "toml"),
    ],
)
def test_format_methods_require_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    extra: str,
) -> None:
    """Format methods provide install guidance when their dependencies are absent."""

    def missing_module(name: str) -> Any:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr("confidantic._config._formats.import_module", missing_module)
    target: Any = (
        FormatConfig if method_name.startswith("model_validate") else FormatConfig()
    )

    with pytest.raises(ImportError, match=rf"install confidantic\[{extra}\]"):
        getattr(target, method_name)(*arguments)


def test_model_dump_toml_requires_nulls_to_be_excluded() -> None:
    """TOML serialization leaves unsupported null values to its writer."""
    with pytest.raises(TypeError, match="NoneType"):
        FormatConfig().model_dump_toml()


def test_make_deserializes_yaml_output() -> None:
    """YAML output can be parsed and resolved through a Make annotation."""
    config = PolymorphicChildConfig(name="child", count=2)
    yaml = cast(Any, import_module("yaml"))

    resolved = PolymorphicContainer.model_validate(
        {
            "item": yaml.safe_load(config.model_dump_yaml(context={"make": True})),
            "items": [],
        }
    ).item

    assert type(resolved) is PolymorphicChildConfig
    assert resolved == config


def test_make_deserializes_toml_output() -> None:
    """TOML output can be parsed and resolved through a Make annotation."""
    config = PolymorphicChildConfig(name="child", count=2)

    resolved = PolymorphicContainer.model_validate(
        {
            "item": tomllib.loads(config.model_dump_toml(context={"make": True})),
            "items": [],
        }
    ).item

    assert type(resolved) is PolymorphicChildConfig
    assert resolved == config
