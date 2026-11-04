"""Check wheel installs without development dependencies or checkout imports."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SMOKE = r"""
import importlib
import importlib.util
import io
import os
import sys
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path

profile, checkout = sys.argv[1:]
modules = {
    "rich": "rich",
    "docstrings": "docstring_parser",
    "yaml": "yaml",
    "toml": "tomli_w",
}
enabled = set(modules) if profile == "all" else {profile}
for extra, module in modules.items():
    assert (importlib.util.find_spec(module) is not None) == (extra in enabled), extra

import confidantic
from confidantic import BaseConfig, ConfigModelDict, Factory

installed_path = Path(confidantic.__file__).resolve()
assert installed_path.is_relative_to(Path(sys.prefix).resolve()), installed_path
assert not installed_path.is_relative_to(Path(checkout).resolve()), installed_path
for module in ("annotations", "configurable", "context", "logging", "paths", "types"):
    importlib.import_module(f"confidantic.{module}")
assert not set(modules.values()).intersection(sys.modules)

class Config(BaseConfig):
    model_config = ConfigModelDict(env_prefix="CONFIDANTIC_SMOKE_")
    value: int = 1

os.environ["CONFIDANTIC_SMOKE_VALUE"] = "7"
config = Config()
assert config.value == 7
assert Config(_cli_parse_args=["--value", "6"]).value == 6
assert Config.model_validate_json('{"value":9}').value == 9
assert Config.model_validate_toml("value = 9").value == 9
assert config.copy(value=8).value == 8
assert config.model_field_sources

class Target:
    def __init__(self, value: int = 2, label: str = "retained") -> None:
        self.value = value
        self.label = label

assert Factory.model_from(Target)().model_resolve().value == 2

class Holder:
    def __init__(self, target: Target = Target()) -> None:
        self.target = target

template = Factory.model_from(Holder, __recursive__=Target)
configured = template(target={"value": 9})
assert isinstance(configured.target, Factory)
resolved = configured.model_resolve()
assert isinstance(resolved.target, Target)
assert (resolved.target.value, resolved.target.label) == (9, "retained")
assert template().model_resolve().target.value == 2
assert not set(modules.values()).intersection(sys.modules)

def feature(extra: str, action: Callable[[], object]) -> object:
    if extra in enabled:
        return action()
    try:
        action()
    except ImportError as error:
        assert f"confidantic[{extra}]" in str(error), error
    else:
        raise AssertionError(f"{extra} unexpectedly worked without its dependency")
    return None

for target in (Config, config):
    method = target.model_info if isinstance(target, type) else target.info
    for output in ("string", "table", "print"):
        with redirect_stdout(io.StringIO()) as captured:
            result = feature("rich", lambda: method(output=output))
        if "rich" in enabled:
            if output == "string":
                assert "value" in result
            elif output == "table":
                assert type(result).__module__ == "rich.table"
            else:
                assert result is None and "value" in captured.getvalue()

for text in ("Summary.\n\nAttributes\n----------\n@attrs", "Summary.\n\nAttributes:\n    @attrs"):
    def documented() -> type[BaseConfig]:
        class Documented(BaseConfig):
            __doc__ = text
            value: int = 1
        return Documented
    result = feature("docstrings", documented)
    if "docstrings" in enabled:
        assert "@attrs" not in result.__doc__
        assert "value" in result.__doc__

yaml_text = feature("yaml", config.model_dump_yaml)
loaded_yaml = feature("yaml", lambda: Config.model_validate_yaml("value: 9"))
if "yaml" in enabled:
    assert "value: 7" in yaml_text and loaded_yaml.value == 9
toml_text = feature("toml", config.model_dump_toml)
if "toml" in enabled:
    assert "value = 7" in toml_text
print(f"{profile}: wheel import, core behavior, and optional features passed")
"""


def main() -> int:
    """Build one wheel and test six fresh installs using this Python interpreter.

    Each environment contains only the wheel's declared runtime dependencies
    and the selected extra. Smoke checks run outside the checkout with isolated
    Python import paths. The temporary build and environments are removed on exit.
    """
    project = Path(__file__).resolve().parent.parent
    with TemporaryDirectory(prefix="confidantic-optional-") as temporary:
        directory = Path(temporary)
        wheels = directory / "wheels"
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(wheels), str(project)],
            check=True,
            cwd=directory,
        )
        (wheel,) = wheels.glob("*.whl")
        for profile in ("core", "rich", "docstrings", "yaml", "toml", "all"):
            environment = directory / profile
            subprocess.run(
                ["uv", "venv", "--python", sys.executable, str(environment)],
                check=True,
                cwd=directory,
            )
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            extras = "" if profile == "core" else f"[{profile}]"
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    f"confidantic{extras} @ {wheel.as_uri()}",
                ],
                check=True,
                cwd=directory,
            )
            subprocess.run(
                [str(python), "-I", "-c", SMOKE, profile, str(project)],
                check=True,
                cwd=directory,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
