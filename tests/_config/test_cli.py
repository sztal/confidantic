"""CLI parsing, factory fields, help policy, and scoped suppression."""

import sys

import pytest
from pydantic import ValidationError
from pydantic_settings import CliSettingsSource

from confidantic import BaseConfig, Factory
from confidantic.annotations import Import
from tests._config.factory_targets import DerivedTarget, SimpleTarget


def test_base_config_instance_cli_help_override_does_not_mutate_model_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-instance CLI override is isolated from the model configuration."""

    class Config(BaseConfig, cli_parse_args=True):
        value: int = 1

    monkeypatch.setattr(sys, "argv", ["config.py", "--help"])

    assert Config(_cli_help=False).value == 1
    assert Config.model_config.get("cli_help") is True


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


def test_cli_boolean_values_are_explicit_for_nested_models() -> None:
    """Nested boolean CLI values use an explicit value by default."""

    class Child(BaseConfig):
        enabled: bool = False

    class Config(BaseConfig):
        child: Child = Child()

    config = Config(_cli_parse_args=["--child.enabled", "true"])

    assert config.child.enabled is True


def test_model_resolve_disables_cli_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target construction cannot consume process command-line arguments."""

    class CliConfig(BaseConfig, cli_parse_args=True):
        value: int = 1

    class Target:
        def __init__(self) -> None:
            self.config = CliConfig()

    monkeypatch.setattr(sys, "argv", ["factory.py", "--value=17"])

    assert Factory.model_from(Target)().model_resolve().config.value == 1


@pytest.mark.parametrize("entry", ["base", "factory"])
@pytest.mark.parametrize("target_fails", [False, True])
def test_factory_resolution_restores_cli_after_nested_construction(
    entry: str, target_fails: bool
) -> None:
    """CLI suppression nests across constructors and resets after exceptions."""
    observed: list[int] = []

    class CliConfig(BaseConfig, cli_parse_args=["--value", "9"]):
        value: int = 1

    class InnerTarget:
        def __init__(self) -> None:
            observed.append(CliConfig().value)

    class Target:
        def __init__(self) -> None:
            Factory.instance_from(InnerTarget).model_resolve()
            observed.append(CliConfig().value)
            if target_fails:
                raise RuntimeError("Target failed")

    class Container(BaseConfig):
        target: Factory[Target]

    factory = Factory.instance_from(Target)
    config = Container(target=factory) if entry == "base" else factory
    if target_fails:
        with pytest.raises(RuntimeError, match="Target failed"):
            config.model_resolve()
    else:
        config.model_resolve()

    assert observed == [1, 1]
    assert CliConfig().value == 9


@pytest.mark.parametrize("help_enabled", [False, True])
def test_factory_cli_help_policy_preserves_nested_options(
    help_enabled: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    """Help policy changes the help flag without removing concrete factory fields."""

    class Config(BaseConfig, cli_help=help_enabled):
        target: Factory[SimpleTarget] = Factory.instance_from(SimpleTarget)

    annotation = Config.model_fields["target"].annotation
    config = Config(_cli_parse_args=["--target.value", "7"])
    assert config.target.model_resolve().value == 7
    assert Config.model_fields["target"].annotation is annotation

    if help_enabled:
        with pytest.raises(SystemExit) as error:
            Config(_cli_parse_args=["--help"])
        assert error.value.code == 0
        assert "--target.value" in capsys.readouterr().out
    else:
        config = Config(_cli_parse_args=["--help", "--target.value", "8"])
        assert config.target.model_resolve().value == 8
        assert capsys.readouterr().out == ""


def test_factory_cli_imports_constrained_class_arguments() -> None:
    """Nested constructor type choices accept importable compatible subclasses."""

    class Target:
        def __init__(
            self, dependency: Import[type[SimpleTarget]] = SimpleTarget
        ) -> None:
            self.dependency = dependency

    class Config(BaseConfig):
        target: Factory[Target] = Factory.instance_from(Target)

    config = Config(
        _cli_parse_args=[
            "--target.dependency",
            "tests._config.factory_targets:DerivedTarget",
        ]
    )
    assert config.target.model_resolve().dependency is DerivedTarget
    with pytest.raises(ValidationError, match="subclass of SimpleTarget"):
        Config(_cli_parse_args=["--target.dependency", "builtins:dict"])


@pytest.mark.parametrize(
    "source_options",
    [
        pytest.param({}, id="default-env-help"),
        pytest.param({"cli_show_env_vars": False}, id="without-env-help"),
    ],
)
def test_supplied_cli_source_keeps_its_parser_and_values(
    source_options: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller's custom CLI source is retained despite automatic-parser options."""

    class Config(BaseConfig, cli_help=False):
        value: int = 1

    monkeypatch.setenv("VALUE", "19")
    assert Config().value == 1

    supplied = CliSettingsSource(
        Config, cli_parse_args=["--value", "7"], **source_options
    )
    help_text = supplied.root_parser.format_help()
    assert "--help" in help_text
    assert "[env:" not in help_text
    config = Config(_cli_settings_source=supplied, _cli_parse_args=False)
    assert config.value == 7
    assert config.model_field_sources["value"] == (CliSettingsSource, Config)


def test_default_cli_help_omits_environment_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Automatic CLI help does not advertise disabled environment input."""

    class Config(BaseConfig):
        value: int = 1

    with pytest.raises(SystemExit) as error:
        Config(_cli_parse_args=["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "--value" in help_text
    assert "[env:" not in help_text


@pytest.mark.parametrize("env_prefix", ["", "APP_"])
@pytest.mark.parametrize("supplied_source", [False, True])
def test_cli_environment_help_can_be_enabled(
    env_prefix: str,
    supplied_source: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both parser entry points honor explicit environment-name help."""

    class Config(BaseConfig, env_prefix=env_prefix, cli_show_env_vars=True):
        value: int = 1

    monkeypatch.setenv(f"{env_prefix}VALUE", "19")
    assert Config().value == 19

    with pytest.raises(SystemExit) as error:
        if supplied_source:
            CliSettingsSource(Config, cli_parse_args=["--help"])
        else:
            Config(_cli_parse_args=["--help"])
    assert error.value.code == 0
    assert f"[env: {env_prefix}VALUE]" in capsys.readouterr().out
