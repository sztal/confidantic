"""Public configuration options and their class and instance overrides."""

from pathlib import Path

import pytest

from confidantic import BaseConfig, ConfigModelDict


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
        "docstring_style",
        "env_file_discovery",
    }

    assert ConfigModelDict.__doc__ is not None
    assert all(option in ConfigModelDict.__doc__ for option in documented_options)
    assert BaseConfig.__doc__ is not None
    assert "ConfigModelDict" in BaseConfig.__doc__
    assert "BaseSettings" in BaseConfig.__doc__
