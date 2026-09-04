"""Tests for the base configuration model."""

import sys
import tomllib
from copy import copy, deepcopy
from enum import Enum
from importlib import import_module
from inspect import signature
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

import pytest
from docstring_parser import DocstringStyle, parse
from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)
from rich.console import Console
from rich.table import Table

from confidantic import BaseConfig, ClassDefaultsSource
from confidantic import ConfigModelDict as ConfigModelDict
from confidantic.annotations import Make


class DocumentedConfig(BaseConfig):
    """Configuration with a source-level field description.

    Attributes
    ----------
    @attrs
    """

    name: str
    """The name of the configuration."""


class SerializedChildConfig(BaseConfig):
    """Configuration nested in a serialized parent."""

    value: int = 1


class SerializedParentConfig(BaseConfig):
    """Configuration containing another configuration."""

    child: SerializedChildConfig = SerializedChildConfig()


class PolymorphicConfig(BaseConfig):
    """Base configuration for marker-driven validation tests."""

    name: str


class PolymorphicChildConfig(PolymorphicConfig):
    """Concrete configuration with a child-only field."""

    count: int = 1


class PolymorphicSiblingConfig(PolymorphicConfig):
    """Sibling configuration used to test subtype constraints."""

    enabled: bool = True


class StrictPolymorphicConfig(PolymorphicConfig):
    """Concrete configuration that forbids undeclared fields."""

    model_config = ConfigModelDict(extra="forbid")


class PolymorphicContainer(BaseModel):
    """Pydantic model with polymorphic configuration fields."""

    item: Make[PolymorphicConfig]
    items: list[Make[PolymorphicConfig]]


class FormatConfig(BaseConfig):
    """Configuration used to test YAML and TOML serialization."""

    name: str = "example"
    nested: dict[str, int] = Field(default_factory=lambda: {"value": 1})
    optional: str | None = None


def _build_config(settings_cls: type[BaseConfig], **kwargs: Any) -> Any:
    return settings_cls(**kwargs)


def _render_with_colors(table: Table) -> str:
    buffer = StringIO()
    Console(
        file=buffer,
        color_system="standard",
        force_terminal=True,
    ).print(table)
    return buffer.getvalue()


def _docstring_attributes(
    settings_cls: type[BaseConfig],
) -> list[tuple[str, str | None]]:
    parsed = parse(settings_cls.__doc__, style=DocstringStyle.NUMPYDOC)
    return [
        (item.arg_name, item.description)
        for item in parsed.params
        if item.args[0] == "attribute"
    ]


def test_base_config_can_be_instantiated() -> None:
    """The public base class is also a valid empty settings model."""
    assert BaseConfig().model_dump() == {}


def test_base_config_find_dotenv_delegates_to_dotenv_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BaseConfig exposes the discovered dotenv path unchanged."""
    monkeypatch.setattr(
        "confidantic._config.base.find_dotenv",
        lambda: "/tmp/project/.env",
    )

    assert BaseConfig.find_dotenv() == "/tmp/project/.env"


def test_base_config_accepts_base_settings_sunder_arguments() -> None:
    """BaseConfig forwards every per-instance Pydantic Settings override."""
    base_settings_options = tuple(
        name
        for name in signature(BaseSettings._settings_init_sources).parameters
        if name != "_init_kwargs"
    )
    config_options = tuple(
        name
        for name in signature(BaseConfig._settings_init_sources).parameters
        if name != "_init_kwargs"
    )

    assert config_options == base_settings_options
    BaseConfig(**dict.fromkeys(base_settings_options))


def test_base_config_accepts_custom_class_and_instance_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom model options support class and leading-underscore forms."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-discovery\n", encoding="utf-8")

    class Config(
        BaseConfig,
        env_file_discovery=True,
        cli_help=False,
    ):
        value: str = "default"

        @classmethod
        def find_dotenv(cls) -> str:
            return str(env_file)

    assert Config.model_config.get("env_file_discovery") is True
    assert Config.model_config.get("cli_help") is False
    assert Config(_env_file_discovery=False).value == "default"
    assert Config(_env_file_discovery=True, _cli_help=False).value == ("from-discovery")


def test_base_config_instance_cli_help_override_does_not_mutate_model_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-instance CLI override is isolated from the model configuration."""

    class Config(BaseConfig, cli_parse_args=True):
        value: int = 1

    monkeypatch.setattr(sys, "argv", ["config.py", "--help"])

    assert Config(_cli_help=False).value == 1
    assert Config.model_config.get("cli_help") is True


def test_config_model_dict_documents_all_settings_options() -> None:
    """The public option reference covers Pydantic Settings and extensions."""
    documented_options = {
        "case_sensitive",
        "nested_model_default_partial_update",
        "env_prefix",
        "env_prefix_target",
        "env_file",
        "env_file_encoding",
        "dotenv_filtering",
        "env_ignore_empty",
        "env_nested_delimiter",
        "env_nested_max_split",
        "env_parse_none_str",
        "env_parse_enums",
        "cli_prog_name",
        "cli_parse_args",
        "cli_parse_none_str",
        "cli_hide_none_type",
        "cli_avoid_json",
        "cli_enforce_required",
        "cli_use_class_docs_for_groups",
        "cli_show_env_vars",
        "cli_exit_on_error",
        "cli_prefix",
        "cli_flag_prefix_char",
        "cli_implicit_flags",
        "cli_ignore_unknown_args",
        "cli_kebab_case",
        "cli_shortcuts",
        "secrets_dir",
        "json_file",
        "json_file_encoding",
        "yaml_file",
        "yaml_file_encoding",
        "yaml_config_section",
        "toml_file",
        "toml_table_header",
        "pyproject_toml_depth",
        "pyproject_toml_table_header",
        "enable_decoding",
        "docstring_set_attributes_section",
        "env_file_discovery",
    }

    assert ConfigModelDict.__doc__ is not None
    assert all(option in ConfigModelDict.__doc__ for option in documented_options)
    assert BaseConfig.__doc__ is not None
    assert "ConfigModelDict" in BaseConfig.__doc__
    assert "BaseSettings" in BaseConfig.__doc__


def test_make_serialization_is_opt_in_and_recursive() -> None:
    """Dump context adds ordered Make directives to nested configurations."""
    config = SerializedParentConfig()

    assert config.model_dump() == {"child": {"value": 1}}
    assert config.model_dump(context={"make": True}) == {
        "@call": "tests.test_config_base:SerializedParentConfig",
        "child": {
            "@call": "tests.test_config_base:SerializedChildConfig",
            "value": 1,
        },
    }
    assert config.model_dump_json(context={"make": True}) == (
        '{"@call":"tests.test_config_base:SerializedParentConfig",'
        '"child":{"@call":"tests.test_config_base:SerializedChildConfig",'
        '"value":1}}'
    )


def test_make_serialization_does_not_use_factory_target_attribute() -> None:
    """Only Factory instances use their target for Make directives."""

    class MisleadingConfig(BaseConfig):
        factory_target: ClassVar[type] = str

    assert MisleadingConfig().model_dump(context={"make": True})["@call"] == (
        "tests.test_config_base:test_make_serialization_does_not_use_factory_target_attribute.<locals>.MisleadingConfig"
    )


def test_make_serialization_preserves_dump_options() -> None:
    """Make directives remain independent from aliases and exclusions."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

    assert Config(VALUE=1).model_dump(
        by_alias=True,
        exclude={"value"},
        context={"make": True},
    ) == {
        "@call": "tests.test_config_base:test_make_serialization_preserves_dump_options.<locals>.Config"
    }


def test_make_deserializes_concrete_subclasses() -> None:
    """Make mappings and JSON resolve to their concrete configuration types."""
    config = PolymorphicChildConfig(name="child", count=2)
    data = config.model_dump(context={"make": True})

    resolved = PolymorphicContainer.model_validate({"item": data, "items": []}).item
    resolved_json = PolymorphicContainer.model_validate_json(
        '{"item":' + config.model_dump_json(context={"make": True}) + ',"items":[]}'
    ).item

    assert type(resolved) is PolymorphicChildConfig
    assert resolved == config
    assert type(resolved_json) is PolymorphicChildConfig
    assert resolved_json == config


def test_make_deserializes_nested_subclasses() -> None:
    """Fields and containers retain concrete types selected by Make directives."""
    child = PolymorphicChildConfig(name="child", count=2)
    sibling = PolymorphicSiblingConfig(name="sibling", enabled=False)

    resolved = PolymorphicContainer.model_validate(
        {
            "item": child.model_dump(context={"make": True}),
            "items": [
                child.model_dump(context={"make": True}),
                sibling.model_dump(context={"make": True}),
            ],
        }
    )

    assert type(resolved.item) is PolymorphicChildConfig
    assert type(resolved.items[0]) is PolymorphicChildConfig
    assert type(resolved.items[1]) is PolymorphicSiblingConfig


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
        "'@call': tests.test_config_base:FormatConfig\n"
        "name: example\n"
        "nested:\n"
        "    value: 1\n"
    )
    assert yaml.safe_load(result) == {
        "@call": "tests.test_config_base:FormatConfig",
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
        '"@call" = "tests.test_config_base:FormatConfig"\n'
        'name = "example"\n\n'
        "[nested]\n"
        "value = 1\n"
    )
    assert tomllib.loads(result) == {
        "@call": "tests.test_config_base:FormatConfig",
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

    def missing_module(_: str) -> Any:
        raise ImportError

    monkeypatch.setattr("confidantic._config.base.import_module", missing_module)
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


def test_base_config_is_frozen_by_default() -> None:
    """Configuration fields cannot be reassigned by default."""

    class Config(BaseConfig):
        value: str = "initial"

    config = Config()

    assert Config.model_config["frozen"] is True  # type: ignore[truthy-function]
    with pytest.raises(ValidationError) as error:
        config.value = "changed"

    assert error.value.errors()[0]["type"] == "frozen_instance"


def test_frozen_config_retains_field_sources() -> None:
    """Frozen construction retains default and explicit field provenance."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(frozen=True)

        value: str = "default"

    assert Config().model_field_sources == {
        "value": (ClassDefaultsSource, Config),
    }
    assert Config(value="explicit").model_field_sources == {
        "value": (InitSettingsSource, Config),
    }


def test_frozen_default_is_inherited_with_other_model_options() -> None:
    """Subclass model options preserve the inherited frozen default."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: str = "initial"

    assert Config.model_config["frozen"] is True  # type: ignore[truthy-function]
    with pytest.raises(ValidationError):
        Config().value = "changed"


def test_frozen_default_can_be_disabled() -> None:
    """Subclasses can opt into mutable configuration fields."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(frozen=False)

        value: str = "initial"

    config = Config()
    config.value = "changed"

    assert config.value == "changed"


def test_copy_protocol_preserves_configuration_state() -> None:
    """Copy protocols retain model state with their standard depth semantics."""

    class Config(BaseConfig):
        value: int = 1
        items: list[int]

        _state: dict[str, list[int]] = PrivateAttr(
            default_factory=lambda: {"items": [1]}
        )

    config = Config(items=[1])

    shallow = copy(config)
    deep = deepcopy(config)
    convenience_shallow = config.copy()
    convenience_deep = config.deepcopy()

    assert isinstance(shallow, Config)
    assert shallow is not config
    assert shallow.items is config.items
    assert shallow._state is config._state
    assert shallow.model_fields_set == config.model_fields_set
    assert shallow.model_field_sources == config.model_field_sources
    assert deep.items == config.items
    assert deep.items is not config.items
    assert deep._state == config._state
    assert deep._state is not config._state
    assert convenience_shallow.items is config.items
    assert convenience_deep.items is not config.items
    with pytest.raises(ValidationError):
        shallow.value = 2


def test_copy_methods_validate_updates_and_retain_provenance() -> None:
    """Convenience copies validate updates without replacing inherited sources."""

    class Config(BaseConfig):
        value: int = 1
        defaulted: str = "default"
        items: list[int]

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    config = Config(value=2, items=[1])

    shallow = config.copy(value="3")
    deep = config.deepcopy(value="4")

    assert shallow.value == 6
    assert deep.value == 8
    assert shallow.model_field_sources == {
        "value": (InitSettingsSource, Config),
        "defaulted": (ClassDefaultsSource, Config),
        "items": (InitSettingsSource, Config),
    }
    assert shallow.model_fields_set == {"value", "items"}
    assert shallow._model_field_sources is not config._model_field_sources
    with pytest.raises(ValidationError):
        config.copy(value="invalid")


def test_mutate_validates_frozen_configuration_in_place() -> None:
    """Frozen configurations can be validated and updated in place explicitly."""

    class Config(BaseConfig):
        value: int = 1
        defaulted: str = "default"

        _state: list[str] = PrivateAttr(default_factory=list)

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    config = Config()
    state = config._state
    original_hash = hash(config)

    assert config.mutate(value="3") is config
    assert config.value == 6
    assert hash(config) != original_hash
    assert config.model_field_sources == {
        "value": (InitSettingsSource, Config),
        "defaulted": (ClassDefaultsSource, Config),
    }
    assert config.model_fields_set == {"value"}
    assert config._state is state
    with pytest.raises(ValidationError):
        config.value = 2

    with pytest.raises(ValidationError):
        config.mutate(value="invalid")

    assert config.value == 6
    assert config.model_fields_set == {"value"}


def test_model_info_builds_table_without_evaluating_factories(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Model metadata renders without constructing default values."""
    factory_calls = 0

    def make_values() -> list[str]:
        nonlocal factory_calls
        factory_calls += 1
        return ["generated"]

    class ParentConfig(BaseConfig):
        inherited: int = 1

    class Config(ParentConfig):
        required: str
        aliased: list[str] = Field(
            default_factory=make_values,
            alias="ALIASED",
            description="[bold]Literal description[/bold]",
        )
        optional: str | None = None

    table = Config.model_info(output="table")

    assert isinstance(table, Table)
    assert table.title == "Config"
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Default",
        "Description",
    ]
    assert len(table.rows) == 4
    assert factory_calls == 0

    rendered = Config.model_info(output="string")

    assert capsys.readouterr().out == ""
    assert "\x1b[" not in rendered
    assert rendered.endswith("\n")
    assert rendered.index("inherited") < rendered.index("required")
    assert "aliased" in rendered
    assert "ALIASED" not in rendered
    assert "list[str]" in rendered
    assert "required" in rendered
    assert "<factory: make_values>" in rendered
    assert "None" in rendered
    assert "[bold]Literal" in rendered
    assert "description[/bold]" in rendered
    assert factory_calls == 0


def test_model_info_controls_header_and_description() -> None:
    """Header and description controls alter only their table features."""

    class Config(BaseConfig):
        value: str = Field("default", description="The value.")

    table = Config.model_info(output="table", header=False, describe=False)

    assert table.title is None
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Default",
    ]


def test_model_info_uses_attribute_docstrings() -> None:
    """Source-level attribute docstrings populate field descriptions."""
    assert DocumentedConfig.model_fields["name"].description == (
        "The name of the configuration."
    )
    assert _docstring_attributes(DocumentedConfig) == [
        ("name", "The name of the configuration.")
    ]
    assert "The name of the configuration." in DocumentedConfig.model_info(
        output="string"
    )


def test_model_docstring_replaces_marker_and_preserves_other_sections() -> None:
    """Generated attributes replace the marker without losing other content."""

    class Config(BaseConfig):
        """Current summary.

        Attributes
        ----------
        @attrs

        Notes
        -----
        Keep this note.
        """

        primary: str = Field(description="Primary value.")
        secondary: int = Field(default=1, alias="SECONDARY")

    assert Config.__doc__ is not None
    parsed = parse(Config.__doc__, style=DocstringStyle.NUMPYDOC)

    assert parsed.short_description == "Current summary."
    assert _docstring_attributes(Config) == [
        ("primary", "Primary value."),
        ("secondary", None),
    ]
    assert "@attrs" not in Config.__doc__
    assert "SECONDARY" not in Config.__doc__
    assert any(
        item.args == ["notes"] and item.description == "Keep this note."
        for item in parsed.meta
    )


def test_model_docstring_marker_includes_inherited_fields() -> None:
    """Marked subclasses describe all effective model fields in order."""

    class ParentConfig(BaseConfig):
        """Parent configuration.

        Attributes
        ----------
        @attrs
        """

        inherited: str = Field(description="Inherited value.")

    class Config(ParentConfig):
        """Child configuration.

        Attributes
        ----------
        @attrs
        """

        direct: int = Field(description="Direct value.")

    assert _docstring_attributes(Config) == [
        ("inherited", "Inherited value."),
        ("direct", "Direct value."),
    ]
    assert _docstring_attributes(ParentConfig) == [("inherited", "Inherited value.")]


def test_model_docstring_generation_can_be_disabled() -> None:
    """The inherited opt-out leaves class docstrings unchanged."""
    original_docstring = "Original documentation.\n\nAttributes\n----------\n@attrs"

    class DisabledConfig(BaseConfig):
        __doc__ = original_docstring
        model_config = ConfigModelDict(
            docstring_set_attributes_section=False,
        )

        value: str = Field(description="Generated description.")

    class ChildConfig(DisabledConfig):
        """Child documentation."""

        child: int

    assert DisabledConfig.__doc__ == original_docstring
    assert ChildConfig.__doc__ == "Child documentation."


def test_model_docstring_without_marker_is_preserved_for_cli_models() -> None:
    """CLI-enabled models preserve docstrings without an opt-in marker."""
    original_docstring = (
        "Original documentation.\n\n"
        "Attributes\n"
        "----------\n"
        "handwritten\n"
        "    Keep this entry."
    )

    class Config(BaseConfig, cli_parse_args=True):
        __doc__ = original_docstring

        value: str = Field(description="Generated description.")

    assert Config.__doc__ == original_docstring


def test_model_docstring_generation_requires_a_docstring_by_default() -> None:
    """Undocumented models do not receive a generated attributes section."""

    class Config(BaseConfig):
        value: str = Field(description="Generated description.")

    assert Config.__doc__ is None


def test_model_docstring_without_marker_is_preserved() -> None:
    """Documented models need a marker before an Attributes section is added."""

    class Config(BaseConfig):
        """Summary without an attributes marker."""

        value: str = Field(description="Generated description.")

    assert Config.__doc__ == "Summary without an attributes marker."


def test_model_docstring_marker_is_replaced_for_cli_models() -> None:
    """CLI-enabled models replace the marker when they explicitly opt in."""

    class Config(BaseConfig, cli_parse_args=True):
        """CLI summary.

        Attributes
        ----------
        @attrs
        """

        value: str = Field(description="Generated description.")

    assert _docstring_attributes(Config) == [("value", "Generated description.")]


def test_fieldless_model_does_not_gain_an_attributes_section() -> None:
    """A model without fields keeps its original docstring unchanged."""

    class Config(BaseConfig):
        """Summary only."""

    assert Config.__doc__ == "Summary only."


def test_model_info_controls_colors() -> None:
    """Colors are disabled by default and enabled only when requested."""

    class Config(BaseConfig):
        required: str
        number: int = 1

    plain_table = Config.model_info(output="table")
    colored_table = Config.model_info(output="table", colors=True)

    assert not plain_table.columns[0].style
    assert colored_table.columns[0].style == "cyan"
    assert "\x1b[" not in _render_with_colors(plain_table)
    assert "\x1b[" in _render_with_colors(colored_table)
    assert "\x1b[" not in Config.model_info(output="string")
    assert "\x1b[" in Config.model_info(output="string", colors=True)


def test_model_info_prints_by_default_and_validates_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default mode prints, while unsupported modes fail clearly."""

    class Config(BaseConfig):
        value: str = "default"

    assert Config.model_info() is None
    printed = capsys.readouterr().out
    assert "Config" in printed
    assert "\x1b[" not in printed

    assert Config.model_info(colors=True) is None
    assert "\x1b[" in capsys.readouterr().out

    invalid_output: Any = "invalid"
    with pytest.raises(ValueError, match="Invalid output mode: 'invalid'"):
        Config.model_info(output=invalid_output)


def test_info_shows_actual_values_without_evaluating_factories_again(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Instance information preserves current Python values and masked secrets."""
    factory_calls = 0

    class Status(Enum):
        ready = "ready"

    class Options(BaseModel):
        enabled: bool

    def make_values() -> list[int]:
        nonlocal factory_calls
        factory_calls += 1
        return [1, 2]

    class Config(BaseConfig):
        name: str = Field("default", alias="NAME", description="The name.")
        status: Status = Status.ready
        path: Path = Path("/d")
        options: Options = Options(enabled=False)
        values: list[int] = Field(default_factory=make_values)
        secret: SecretStr = SecretStr("default-secret")

    config = Config(
        NAME="current",
        path=Path("/x"),
        options=Options(enabled=True),
        secret=SecretStr("actual-secret"),
    )
    assert factory_calls == 1

    table = config.info(output="table")

    assert isinstance(table, Table)
    assert table.title == "Config"
    assert [column.header for column in table.columns] == [
        "Option",
        "Value",
        "Description",
    ]
    assert len(table.rows) == 6

    rendered = config.info(output="string", describe=False)

    assert capsys.readouterr().out == ""
    assert "NAME" not in rendered
    assert "'current'" in rendered
    assert "'default'" not in rendered
    assert "Status.ready" in rendered
    assert "PosixPath('/x')" in rendered
    assert "Options(enabled=True)" in rendered
    assert "[1, 2]" in rendered
    assert "actual-secret" not in rendered
    assert "default-secret" not in rendered
    assert "**********" in rendered
    assert "The name." in config.info(output="string")
    assert factory_calls == 1


def test_info_controls_table_and_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Instance information mirrors model display and output controls."""

    class Config(BaseConfig):
        value: str = "default"

    config = Config(value="current")
    plain_table = config.info(output="table")
    table = config.info(
        output="table",
        header=False,
        describe=False,
        colors=True,
        types=True,
    )

    assert table.title is None
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Value",
    ]
    assert table.columns[0].style == "cyan"
    assert "\x1b[" not in _render_with_colors(plain_table)
    assert "\x1b[" in _render_with_colors(table)
    assert "\x1b[" not in config.info(output="string")
    assert "\x1b[" in config.info(output="string", colors=True)
    assert capsys.readouterr().out == ""

    assert config.info() is None
    assert "\x1b[" not in capsys.readouterr().out

    invalid_output: Any = "invalid"
    with pytest.raises(ValueError, match="Invalid output mode: 'invalid'"):
        config.info(output=invalid_output)


def test_cli_parsing_is_disabled_in_jupyterlike_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kernel arguments are ignored when a config enables CLI parsing."""
    monkeypatch.setitem(sys.modules, "ipykernel", object())
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipykernel_launcher.py", "-f", "kernel.json"],
    )

    class Config(BaseConfig, cli_parse_args=True):
        value: str = "from-default"

    assert Config().value == "from-default"


def test_class_defaults_source_is_public() -> None:
    """The public source loads only defaults declared at its class level."""

    class ParentConfig(BaseConfig):
        inherited: str = "inherited"

    class Config(ParentConfig):
        local: int = Field(1, alias="LOCAL")
        required: str

    assert ClassDefaultsSource(Config)() == {"LOCAL": 1}
    assert ClassDefaultsSource(Config, {"inherited"})() == {"inherited": "inherited"}
    assert ClassDefaultsSource(Config, set())() == {}
    assert ClassDefaultsSource(Config, {"unknown"})() == {}


def test_class_defaults_source_supports_arbitrary_types() -> None:
    """Static defaults respect a model's arbitrary-types configuration."""

    class Dependency:
        pass

    dependency = Dependency()

    class Config(BaseConfig, arbitrary_types_allowed=True):
        value: Dependency = dependency

    assert isinstance(ClassDefaultsSource(Config)()["value"], Dependency)
    assert isinstance(Config().value, Dependency)


def test_model_field_sources_track_defaults_and_init() -> None:
    """Field sources identify both resolution and inheritance coordinates."""

    class Config(BaseConfig):
        value: str = "from-default"

    assert Config().model_field_sources == {"value": (ClassDefaultsSource, Config)}
    assert Config(value="from-init").model_field_sources == {
        "value": (InitSettingsSource, Config)
    }


def test_model_field_sources_track_standard_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Built-in sources expose their exact source and configuration classes."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-dotenv\n", encoding="utf-8")
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "value").write_text("from-secret", encoding="utf-8")

    class Config(BaseConfig):
        value: str = "from-default"

    cli = _build_config(
        Config,
        _cli_parse_args=["--value=from-cli"],
        _env_file=env_file,
        _secrets_dir=secrets_dir,
    )
    assert cli.model_field_sources["value"] == (CliSettingsSource, Config)

    monkeypatch.setenv("VALUE", "from-environment")
    environment = _build_config(
        Config,
        _env_file=env_file,
        _secrets_dir=secrets_dir,
    )
    assert environment.model_field_sources["value"] == (
        EnvSettingsSource,
        Config,
    )

    monkeypatch.delenv("VALUE")
    dotenv = _build_config(Config, _env_file=env_file, _secrets_dir=secrets_dir)
    assert dotenv.model_field_sources["value"] == (DotEnvSettingsSource, Config)

    secret = _build_config(Config, _env_file=None, _secrets_dir=secrets_dir)
    assert secret.model_field_sources["value"] == (SecretsSettingsSource, Config)


def test_model_field_sources_track_mro_and_nested_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coordinates retain MRO owners and top-level nested priority."""
    monkeypatch.setenv("CHILD_OPTIONS", '{"child": "environment"}')
    monkeypatch.setenv("PARENT_INHERITED", "environment")

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str = "parent-default"
        parent_default: str = "parent-default"
        options: dict[str, str] = Field(default={"parent": "default"})

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        factory: list[str] = Field(default_factory=list)

    config = ChildConfig()

    assert config.options == {"child": "environment", "parent": "default"}
    assert config.model_field_sources == {
        "inherited": (EnvSettingsSource, ParentConfig),
        "parent_default": (ClassDefaultsSource, ParentConfig),
        "options": (EnvSettingsSource, ChildConfig),
        "factory": (ClassDefaultsSource, ChildConfig),
    }


def test_model_field_sources_use_names_and_retain_input_provenance() -> None:
    """Aliases and validators do not replace settings-source provenance."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    default = _build_config(Config)
    explicit = _build_config(Config, VALUE="4")

    assert default.model_field_sources == {"value": (ClassDefaultsSource, Config)}
    assert explicit.value == 8
    assert explicit.model_field_sources == {"value": (InitSettingsSource, Config)}
    assert explicit.model_dump() == {"value": 8}
    assert explicit.model_fields_set == {"value"}
    with pytest.raises(TypeError):
        explicit.model_field_sources["value"] = (
            ClassDefaultsSource,
            Config,
        )


def test_model_field_sources_preserve_custom_source_identity() -> None:
    """Custom settings sources run once and retain their exact class."""
    calls = 0

    class CustomSource(InitSettingsSource):
        def __call__(self) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return super().__call__()

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (CustomSource(settings_cls, {"value": "from-custom"}),)

    config = _build_config(Config)

    assert config.model_field_sources == {"value": (CustomSource, Config)}
    assert calls == 1


def test_model_field_sources_omit_bare_callable_sources() -> None:
    """Sources without a settings-class axis remain usable but untracked."""

    def custom_source() -> dict[str, str]:
        return {"value": "from-custom"}

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (custom_source,)  # type: ignore[return-value]

    config = _build_config(Config)

    assert config.value == "from-custom"
    assert config.model_field_sources == {}


def test_child_default_precedes_parent_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child default resolves before sources configured on its parent."""
    monkeypatch.setenv("PARENT_VALUE", "from-parent-environment")
    monkeypatch.setenv("PARENT_INHERITED", "from-parent-environment")

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        value: str = "from-parent-default"
        inherited: str = "from-parent-default"

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        value: str = "from-child-default"

    config = ChildConfig()

    assert config.value == "from-child-default"
    assert config.inherited == "from-parent-environment"


def test_standard_source_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Built-in sources retain Pydantic Settings priority."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-dotenv\n", encoding="utf-8")
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "value").write_text("from-secret", encoding="utf-8")
    monkeypatch.setenv("VALUE", "from-environment")

    class Config(BaseConfig):
        value: str = "from-default"

    assert (
        _build_config(
            Config,
            value="from-init",
            _cli_parse_args=["--value=from-cli"],
            _env_file=env_file,
            _secrets_dir=secrets_dir,
        ).value
        == "from-cli"
    )
    assert (
        _build_config(
            Config,
            value="from-init",
            _env_file=env_file,
            _secrets_dir=secrets_dir,
        ).value
        == "from-init"
    )
    assert (
        _build_config(Config, _env_file=env_file, _secrets_dir=secrets_dir).value
        == "from-environment"
    )

    monkeypatch.delenv("VALUE")
    assert (
        _build_config(Config, _env_file=env_file, _secrets_dir=secrets_dir).value
        == "from-dotenv"
    )
    assert (
        _build_config(Config, _env_file=None, _secrets_dir=secrets_dir).value
        == "from-secret"
    )
    assert (
        _build_config(Config, _env_file=None, _secrets_dir=None).value == "from-default"
    )


def test_dotenv_filters_keys_by_each_mro_prefix(tmp_path: Path) -> None:
    """Dotenv sources load their level's prefix and ignore unrelated keys."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHILD_VALUE=from-child\nPARENT_INHERITED=from-parent\nUNRELATED=ignored\n",
        encoding="utf-8",
    )

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        value: str

    config = _build_config(ChildConfig, _env_file=env_file)

    assert config.model_dump() == {
        "inherited": "from-parent",
        "value": "from-child",
    }


def test_dotenv_ignores_undeclared_unprefixed_keys(tmp_path: Path) -> None:
    """Unprefixed dotenv files provide declared fields without extra errors."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "VALUE=from-dotenv\nUNRELATED=ignored\n",
        encoding="utf-8",
    )

    class Config(BaseConfig):
        value: str

    assert _build_config(Config, _env_file=env_file).value == "from-dotenv"


def test_dotenv_discovery_is_opt_in() -> None:
    """An absent dotenv file does not invoke discovery by default."""

    class Config(BaseConfig):
        value: str = "from-default"

        @classmethod
        def find_dotenv(cls) -> str:
            raise AssertionError("dotenv discovery should be disabled")

    assert _build_config(Config, _env_file=None).value == "from-default"


@pytest.mark.parametrize("options", ({}, {"_env_file": None}))
def test_dotenv_discovery_uses_concrete_class_once_across_mro(
    tmp_path: Path,
    options: dict[str, object],
) -> None:
    """A concrete config discovers one dotenv file for every MRO level."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHILD_VALUE=from-child\nPARENT_INHERITED=from-parent\n",
        encoding="utf-8",
    )
    calls = 0

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(
            env_file_discovery=True,
            env_prefix="CHILD_",
        )

        value: str

        @classmethod
        def find_dotenv(cls) -> str:
            nonlocal calls
            calls += 1
            return str(env_file)

    config = _build_config(ChildConfig, **options)

    assert config.model_dump() == {
        "inherited": "from-parent",
        "value": "from-child",
    }
    assert calls == 1


def test_explicit_dotenv_file_bypasses_discovery(tmp_path: Path) -> None:
    """An explicit dotenv file remains authoritative over discovery."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-explicit\n", encoding="utf-8")

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_file_discovery=True)

        value: str

        @classmethod
        def find_dotenv(cls) -> str:
            raise AssertionError("explicit dotenv files bypass discovery")

    config = _build_config(Config, _env_file=env_file)

    assert config.value == "from-explicit"
    assert config.model_field_sources == {"value": (DotEnvSettingsSource, Config)}


def test_nested_values_merge_across_mro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lower MRO levels fill missing nested keys without replacing child keys."""
    monkeypatch.setenv(
        "CHILD_OPTIONS",
        '{"shared": "child-env", "child_env": "child-env"}',
    )
    monkeypatch.setenv(
        "PARENT_OPTIONS",
        '{"shared": "parent-env", "parent_env": "parent-env"}',
    )

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        options: dict[str, str] = Field(
            default={
                "shared": "parent-default",
                "parent_default": "parent-default",
            }
        )

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        options: dict[str, str] = Field(
            default={
                "shared": "child-default",
                "child_default": "child-default",
            }
        )

    assert ChildConfig().options == {
        "shared": "child-env",
        "child_env": "child-env",
        "child_default": "child-default",
        "parent_env": "parent-env",
        "parent_default": "parent-default",
    }


def test_nested_model_defaults_merge_across_mro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested model defaults contribute missing values across MRO levels."""
    monkeypatch.setenv("CHILD_OPTIONS", '{"child": 2}')

    class Options(BaseModel):
        child: int = 0
        parent: int = 0

    class ParentConfig(BaseConfig):
        options: Options = Field(default=Options(parent=1))

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

    assert ChildConfig().options == Options(child=2, parent=1)


def test_default_factory_blocks_parent_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child factory stays lazy and blocks the corresponding parent field."""
    monkeypatch.setenv("PARENT_VALUES", '["from-parent-environment"]')
    calls = 0

    def make_values() -> list[str]:
        nonlocal calls
        calls += 1
        return ["from-child-factory"]

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        values: list[str] = Field(default=["from-parent-default"])

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        values: list[str] = Field(default_factory=make_values)

    first = ChildConfig()
    second = ChildConfig()

    assert first.values == ["from-child-factory"]
    assert second.values == ["from-child-factory"]
    assert first.values is not second.values
    assert calls == 2


def test_validated_data_default_factory_keeps_pydantic_semantics() -> None:
    """Factories that consume validated data are evaluated by Pydantic."""

    class Config(BaseConfig):
        seed: int = 3
        values: list[int] = Field(default_factory=lambda data: [data["seed"]])

    assert Config().values == [3]


def test_partial_cli_update_preserves_nested_factory_model() -> None:
    """A CLI patch retains the factory model's concrete type and defaults."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2
        child_only: int = 3

    class Config(BaseConfig):
        nested: Nested = Field(default_factory=NestedChild)

    config = _build_config(Config, _cli_parse_args=["--nested.x=11"])

    assert type(config.nested) is NestedChild
    assert config.nested == NestedChild(x=11)


def test_nested_factory_model_is_partially_updated_from_env_and_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mapping sources patch the factory model and retain their provenance."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    class Config(BaseConfig):
        nested: Nested = Field(default_factory=NestedChild)

    monkeypatch.setenv("NESTED__X", "11")
    environment = Config()
    monkeypatch.delenv("NESTED__X")
    explicit_mapping = _build_config(Config, nested={"x": "12"})

    assert type(environment.nested) is NestedChild
    assert environment.nested == NestedChild(x=11)
    assert environment.model_field_sources["nested"] == (EnvSettingsSource, Config)
    assert type(explicit_mapping.nested) is NestedChild
    assert explicit_mapping.nested == NestedChild(x=12)
    assert explicit_mapping.model_field_sources["nested"] == (
        InitSettingsSource,
        Config,
    )


def test_partial_update_uses_static_or_explicit_nested_model_baseline() -> None:
    """A patch retains the concrete type and current values of its baseline."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2
        child_only: int = 3

    class Config(BaseConfig):
        nested: Nested = NestedChild(y=7)

    static = _build_config(Config, _cli_parse_args=["--nested.x=11"])
    base = Nested(x=2, y=8)
    explicit = Config(nested=base)
    patched_explicit = _build_config(
        Config,
        nested=base,
        _cli_parse_args=["--nested.x=12"],
    )

    assert type(static.nested) is NestedChild
    assert static.nested == NestedChild(x=11, y=7)
    assert explicit.nested is base
    assert type(patched_explicit.nested) is Nested
    assert patched_explicit.nested == Nested(x=12, y=8)


def test_partial_update_evaluates_validated_data_model_factory_once() -> None:
    """A partial update defers one data-aware factory call to validation."""
    calls = 0

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    def make_nested(data: dict[str, Any]) -> NestedChild:
        nonlocal calls
        calls += 1
        return NestedChild(y=data["seed"])

    class Config(BaseConfig):
        seed: int = 3
        nested: Nested = Field(default_factory=make_nested)

    config = _build_config(
        Config,
        seed="7",
        _cli_parse_args=["--nested.x=11"],
    )

    assert type(config.nested) is NestedChild
    assert config.nested == NestedChild(x=11, y=7)
    assert calls == 1


def test_mapping_source_does_not_evaluate_non_model_factory() -> None:
    """A supplied mapping does not evaluate an unrelated mapping factory."""
    calls = 0

    def make_values() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"default": 1}

    class Config(BaseConfig):
        values: dict[str, int] = Field(default_factory=make_values)

    config = Config(values={"provided": 2})

    assert config.values == {"provided": 2}
    assert calls == 0


def test_partial_update_recurses_through_plain_pydantic_models() -> None:
    """Direct BaseModel fields retain runtime types at every nested level."""

    class Inner(BaseModel):
        x: int = Field(1, alias="X")
        y: int = 1

        @field_validator("x")
        @classmethod
        def double_x(cls, value: int) -> int:
            return value * 2

    class InnerChild(Inner):
        y: int = 2
        child_only: int = 3

    class Outer(BaseModel):
        inner: Inner = InnerChild(X=1)

    class OuterChild(Outer):
        outer_only: int = 4

    class Config(BaseConfig):
        nested: Outer = Field(default_factory=OuterChild)

    config = _build_config(Config, nested={"inner": {"X": "5"}})

    assert type(config.nested) is OuterChild
    assert type(config.nested.inner) is InnerChild
    assert config.nested.inner == InnerChild(X=5)
    assert config.nested.model_fields_set == {"inner"}
    assert config.nested.inner.model_fields_set == {"x"}


def test_nested_model_partial_update_can_be_disabled() -> None:
    """Class and instance opt-outs retain the original Pydantic behavior."""

    class Nested(BaseModel):
        x: int = 1
        y: int = 1

    class NestedChild(Nested):
        y: int = 2

    class Config(BaseConfig):
        model_config = ConfigModelDict(
            nested_model_default_partial_update=False,
        )

        nested: Nested = Field(default_factory=NestedChild)

    class InstanceOverrideConfig(BaseConfig):
        nested: Nested = Field(default_factory=NestedChild)

    configured = _build_config(Config, _cli_parse_args=["--nested.x=11"])
    overridden = _build_config(
        InstanceOverrideConfig,
        _nested_model_default_partial_update=False,
        _cli_parse_args=["--nested.x=12"],
    )

    assert type(configured.nested) is Nested
    assert configured.nested == Nested(x=11)
    assert type(overridden.nested) is Nested
    assert overridden.nested == Nested(x=12)


def test_discriminated_nested_model_update_selects_replacement_variant() -> None:
    """A discriminator selects a variant without values from the default."""

    class First(BaseModel):
        kind: Literal["first"] = "first"
        shared: int = 7

    class Second(BaseModel):
        kind: Literal["second"] = "second"
        shared: int = 2

    class Config(BaseConfig):
        nested: First | Second = Field(
            default=First(),
            discriminator="kind",
        )

    config = _build_config(Config, nested={"kind": "second"})

    assert type(config.nested) is Second
    assert config.nested == Second()


def test_aliases_validators_and_fields_set_are_preserved() -> None:
    """MRO resolution still delegates aliases and validation to Pydantic."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    default = _build_config(Config)
    explicit = _build_config(Config, VALUE="4")

    assert default.value == 2
    assert default.model_fields_set == set()
    assert explicit.value == 8
    assert explicit.model_fields_set == {"value"}


def test_values_equal_to_defaults_are_in_fields_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit sources retain provenance when their values equal defaults."""

    class Config(BaseConfig):
        value: str = "same"

    default = Config()
    explicit = Config(value="same")
    monkeypatch.setenv("VALUE", "same")
    environment = Config()

    assert default.model_fields_set == set()
    assert explicit.model_fields_set == {"value"}
    assert environment.model_fields_set == {"value"}
    assert default.model_field_sources["value"] == (ClassDefaultsSource, Config)
    assert explicit.model_field_sources["value"] == (InitSettingsSource, Config)
    assert environment.model_field_sources["value"] == (EnvSettingsSource, Config)


@pytest.mark.parametrize(
    ("custom_first", "expected"),
    [(True, "from-custom"), (False, "from-init")],
)
def test_subclass_controls_custom_source_priority(
    custom_first: bool,
    expected: str,
) -> None:
    """Structured-style custom sources keep their subclass-selected position."""

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            custom = InitSettingsSource(
                settings_cls,
                {"value": "from-custom"},
            )
            standard = (
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )
            return (custom, *standard) if custom_first else (init_settings, custom)

    assert Config(value="from-init").value == expected


def test_c3_mro_controls_duplicate_defaults() -> None:
    """The first declaration in the concrete C3 MRO has priority."""

    class RootConfig(BaseConfig):
        root: str = "root"

    class LeftConfig(RootConfig):
        value: str = "left"

    class RightConfig(RootConfig):
        value: str = "right"
        right: str = "right"

    class Config(LeftConfig, RightConfig):
        pass

    config = Config()

    assert config.value == "left"
    assert config.root == "root"
    assert config.right == "right"
    assert config.model_field_sources == {
        "root": (ClassDefaultsSource, RootConfig),
        "value": (ClassDefaultsSource, LeftConfig),
        "right": (ClassDefaultsSource, RightConfig),
    }


def test_missing_required_field_raises_validation_error() -> None:
    """Required fields remain errors after all MRO levels are exhausted."""

    class Config(BaseConfig):
        value: str

    with pytest.raises(ValidationError):
        _build_config(Config)
