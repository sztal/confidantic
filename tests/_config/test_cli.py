"""CLI parsing, factory fields, help policy, and scoped suppression."""

import sys
from enum import Enum
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_settings import CliSettingsSource

from confidantic import BaseConfig, Factory
from confidantic.annotations import CommaDelimited, Import
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
        f: int = 1

    class RequiredConfig(BaseConfig, cli_parse_args=True, cli_enforce_required=True):
        value: int

    assert Config().value == "from-default"
    assert Config().f == 1
    assert RequiredConfig(value=7).value == 7
    assert BaseConfig(_cli_parse_args=True) == BaseConfig()


def test_cli_explicit_sequences_are_parsed_in_jupyterlike_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit CLI argument sequences still parse inside Jupyter-like runtimes."""
    shell = type("ZMQInteractiveShell", (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "ipykernel", object())
    monkeypatch.setattr(
        sys,
        "orig_argv",
        ["python", "-m", "ipykernel_launcher", "--f=/tmp/kernel.json"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["/site-packages/ipykernel_launcher.py", "--f=/tmp/kernel.json"],
    )

    class Config(BaseConfig, cli_parse_args=True):
        param: float | CommaDelimited[tuple[float, float]] = 0.0

    class ExplicitConfig(BaseConfig, cli_parse_args=["--param=0.2"]):
        param: float = 0.0

    assert Config().param == 0.0
    assert Config(_cli_parse_args=["--param=0.1"]).param == 0.1
    assert Config(_cli_parse_args=["--param=0.1,0.2"]).param == (0.1, 0.2)
    assert ExplicitConfig().param == 0.2


@pytest.mark.parametrize(
    ("orig_argv", "argv"),
    [
        (
            ["python", "-m", "ipykernel_launcher", "-f", "kernel.json"],
            ["/env/ipykernel_launcher.py", "-f", "kernel.json"],
        ),
        (
            [
                "python",
                "-X",
                "frozen_modules=off",
                "-m",
                "spyder_kernels.console",
                "-f",
                "kernel.json",
            ],
            ["/env/spyder_kernels/console/__main__.py", "-f", "kernel.json"],
        ),
        (
            ["python", "-u", "/env/custom_kernel.py", "-f", "kernel.json"],
            ["/env/custom_kernel.py", "-f", "kernel.json"],
        ),
        (
            ["python", "-c", "launch_kernel()", "-f", "kernel.json"],
            ["-c", "-f", "kernel.json"],
        ),
        (
            [],
            ["/env/custom_kernel.py", "-f", "kernel.json"],
        ),
    ],
)
def test_cli_jupyter_kernel_argv_is_suppressed_across_launch_styles(
    orig_argv: list[str],
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Untouched kernel launch arguments are ignored across kernel launchers."""
    shell = type("ZMQInteractiveShell", (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "ipykernel", object())
    monkeypatch.setattr(sys, "orig_argv", orig_argv)
    monkeypatch.setattr(sys, "argv", argv)
    if not orig_argv:
        monkeypatch.setitem(sys.modules, "__main__", ModuleType("__main__"))

    class Config(BaseConfig, cli_parse_args=True, cli_ignore_unknown_args=False):
        f: int = 1

    assert Config().f == 1


def test_cli_replaced_argv_and_non_kernel_ipykernel_imports_still_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual sys.argv replacement and CLI scripts importing ipykernel still parse."""

    class Config(BaseConfig, cli_parse_args=True):
        value: str = "from-default"

    # Manual sys.argv replacement inside an active ZMQ kernel shell.
    shell = type("ZMQInteractiveShell", (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "ipykernel", object())
    monkeypatch.setattr(
        sys,
        "orig_argv",
        ["python", "-m", "ipykernel_launcher", "-f", "kernel.json"],
    )
    monkeypatch.setattr(sys, "argv", ["app.py", "--value=from-replaced-argv"])
    assert Config().value == "from-replaced-argv"

    # Plain CLI script that merely imported ipykernel (no active ZMQ shell).
    monkeypatch.setattr(ipython, "get_ipython", lambda: None, raising=False)
    monkeypatch.setattr(
        sys, "orig_argv", ["python", "script.py", "--value=from-script"]
    )
    monkeypatch.setattr(sys, "argv", ["script.py", "--value=from-script"])
    assert Config().value == "from-script"


def test_cli_ipython_run_magic_parses_script_args_in_jupyterlike_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """IPython %run scripts receive CLI arguments inside a notebook kernel."""
    from IPython.core.interactiveshell import InteractiveShell

    kernel_argv = ["/env/ipykernel_launcher.py", "-f", "kernel.json"]
    kernel_orig_argv = ["python", "-m", "ipykernel_launcher", "-f", "kernel.json"]

    shell = InteractiveShell()
    zmq_shell = type("ZMQInteractiveShell", (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: zmq_shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "ipykernel", object())
    monkeypatch.setattr(sys, "orig_argv", kernel_orig_argv)
    monkeypatch.setattr(sys, "argv", kernel_argv)

    script = tmp_path / "run_cli.py"
    script.write_text(
        "from confidantic import BaseConfig\n"
        "from confidantic.annotations import CommaDelimited\n"
        "class RunConfig(BaseConfig, cli_parse_args=True):\n"
        "    param: float | CommaDelimited[tuple[float, float]] = 0.0\n"
        "result = RunConfig().param\n",
        encoding="utf-8",
    )

    class CellConfig(BaseConfig, cli_parse_args=True):
        f: int = 1

    assert CellConfig().f == 1

    shell.run_line_magic("run", f"{script} --param=0.1")
    assert shell.user_ns["result"] == 0.1

    shell.run_line_magic("run", f"-i {script} --param=0.2,0.3")
    assert shell.user_ns["result"] == (0.2, 0.3)

    assert CellConfig().f == 1


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

    assert Factory.model_from(Target)().instance().config.value == 1


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
            Factory.instance_from(InnerTarget).instance()
            observed.append(CliConfig().value)
            if target_fails:
                raise RuntimeError("Target failed")

    class Container(BaseConfig):
        target: Factory[Target]

    factory = Factory.instance_from(Target)
    config = Container(target=factory) if entry == "base" else factory
    construct = config.model_resolve if entry == "base" else config.instance
    if target_fails:
        with pytest.raises(RuntimeError, match="Target failed"):
            construct()
    else:
        construct()

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
    assert config.target.instance().value == 7
    assert Config.model_fields["target"].annotation is annotation

    if help_enabled:
        with pytest.raises(SystemExit) as error:
            Config(_cli_parse_args=["--help"])
        assert error.value.code == 0
        assert "--target.value" in capsys.readouterr().out
    else:
        config = Config(_cli_parse_args=["--help", "--target.value", "8"])
        assert config.target.instance().value == 8
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
    assert config.target.instance().dependency is DerivedTarget
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


@pytest.mark.parametrize("help_enabled", [True, False])
def test_cli_nested_models_propagate_union_no_decode_without_mutating_plain_models(
    help_enabled: bool,
) -> None:
    """Nested plain BaseModel, BaseConfig, and Factory union-NoDecode fields parse cleanly."""

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    class PlainNested(BaseModel):
        floats: float | CommaDelimited[list[float]] = 0.0
        text: str | CommaDelimited[tuple[str, str]] = "a"
        color: Color | CommaDelimited[tuple[Color, Color]] = Color.RED

    class ConfigNested(BaseConfig):
        floats: float | CommaDelimited[list[float]] = 0.0

    class Target:
        def __init__(self, floats: float | CommaDelimited[list[float]] = 0.0) -> None:
            self.floats = floats

    class Root(BaseConfig, cli_parse_args=True, cli_help=help_enabled):
        plain: PlainNested = PlainNested()
        nested: ConfigNested = ConfigNested()
        target: Factory[Target] = Factory.instance_from(Target)

    config = Root(
        _cli_parse_args=[
            "--plain.floats=0.1",
            "--plain.text=1",
            "--plain.color=RED",
            "--nested.floats=0.2",
            "--target.floats=0.3",
        ]
    )

    assert config.plain.floats == 0.1
    assert config.plain.text == "1"
    assert config.plain.color is Color.RED
    assert config.nested.floats == 0.2
    assert config.target.instance().floats == 0.3
    assert config.model_field_sources["plain"] == (CliSettingsSource, Root)
    assert config.model_field_sources["nested"] == (CliSettingsSource, Root)
    assert config.model_field_sources["target"] == (CliSettingsSource, Root)
    assert PlainNested.model_fields["floats"].metadata == []
    assert PlainNested.model_fields["text"].metadata == []
    assert PlainNested.model_fields["color"].metadata == []
