"""Tests for the base configuration model."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)
from rich.table import Table

from confidantic import BaseConfig, ClassDefaultsSource


class DocumentedConfig(BaseConfig):
    """Configuration with a source-level field description."""

    name: str
    """The name of the configuration."""


def _build_config(settings_cls: type[BaseConfig], **kwargs: Any) -> Any:
    return settings_cls(**kwargs)


def test_base_config_can_be_instantiated() -> None:
    """The public base class is also a valid empty settings model."""
    assert BaseConfig().model_dump() == {}


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
    assert "The name of the configuration." in DocumentedConfig.model_info(
        output="string"
    )


def test_model_info_controls_colors() -> None:
    """Colors are disabled by default and enabled only when requested."""

    class Config(BaseConfig):
        required: str

    plain_table = Config.model_info(output="table")
    colored_table = Config.model_info(output="table", colors=True)

    assert not plain_table.columns[0].style
    assert colored_table.columns[0].style == "cyan"
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
        "Type",
        "Value",
        "Default",
        "Description",
    ]
    assert len(table.rows) == 6

    rendered = config.info(output="string", describe=False)

    assert capsys.readouterr().out == ""
    assert "NAME" not in rendered
    assert "'current'" in rendered
    assert "'default'" in rendered
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
    table = config.info(
        output="table",
        header=False,
        describe=False,
        colors=True,
    )

    assert table.title is None
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Value",
        "Default",
    ]
    assert table.columns[0].style == "cyan"
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
        model_config = SettingsConfigDict(env_prefix="PARENT_")

        inherited: str = "parent-default"
        parent_default: str = "parent-default"
        options: dict[str, str] = Field(default={"parent": "default"})

    class ChildConfig(ParentConfig):
        model_config = SettingsConfigDict(env_prefix="CHILD_")

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
        model_config = SettingsConfigDict(env_prefix="PARENT_")

        value: str = "from-parent-default"
        inherited: str = "from-parent-default"

    class ChildConfig(ParentConfig):
        model_config = SettingsConfigDict(env_prefix="CHILD_")

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
        model_config = SettingsConfigDict(env_prefix="PARENT_")

        inherited: str

    class ChildConfig(ParentConfig):
        model_config = SettingsConfigDict(env_prefix="CHILD_")

        value: str

    config = _build_config(ChildConfig, _env_file=env_file)

    assert config.model_dump() == {
        "inherited": "from-parent",
        "value": "from-child",
    }


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
        model_config = SettingsConfigDict(env_prefix="PARENT_")

        options: dict[str, str] = Field(
            default={
                "shared": "parent-default",
                "parent_default": "parent-default",
            }
        )

    class ChildConfig(ParentConfig):
        model_config = SettingsConfigDict(env_prefix="CHILD_")

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
        model_config = SettingsConfigDict(env_prefix="CHILD_")

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
        model_config = SettingsConfigDict(env_prefix="PARENT_")

        values: list[str] = Field(default=["from-parent-default"])

    class ChildConfig(ParentConfig):
        model_config = SettingsConfigDict(env_prefix="CHILD_")

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
