"""Optional features fail locally without affecting core configuration behavior."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


def _run(
    directory: Path,
    code: str,
    blocked: tuple[str, ...],
    *,
    missing_name: str | None = None,
    import_error: bool = False,
) -> None:
    """Block imports before loading Confidantic in a fresh source-backed process."""
    script = directory / "optional_features.py"
    setup = f"""
        import sys
        from importlib.abc import MetaPathFinder
        from typing import Any

        class BlockOptional(MetaPathFinder):
            def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
                if any(fullname == name or fullname.startswith(name + ".") for name in {blocked!r}):
                    if {import_error!r}:
                        raise ImportError("broken optional package")
                    name = {missing_name!r} or fullname
                    raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)

        sys.meta_path.insert(0, BlockOptional())
    """
    script.write_text(dedent(setup) + "\n" + dedent(code))
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_does_not_import_optional_packages(tmp_path: Path) -> None:
    """Core imports, factories, TOML loading, and attribute extraction stay usable."""
    _run(
        tmp_path,
        '''
        import importlib
        from confidantic import BaseConfig, Factory

        for name in ("annotations", "configurable", "context", "logging", "paths", "types"):
            importlib.import_module(f"confidantic.{name}")

        class Config(BaseConfig):
            value: int = 1
            """Extracted without docstring-parser."""

        assert Config.model_fields["value"].description == "Extracted without docstring-parser."
        assert Config(value="2").value == 2
        assert Config(_cli_parse_args=["--value", "6"]).value == 6
        assert Config.model_validate_toml("value = 3").value == 3
        assert Config().copy(value=4).value == 4
        assert Config().model_field_sources

        class Target:
            def __init__(self, value: int = 5, label: str = "retained") -> None:
                self.value = value
                self.label = label

        assert Factory.model_from(Target)().model_resolve().value == 5

        class Holder:
            def __init__(self, target: Target = Target()) -> None:
                self.target = target

        template = Factory.model_from(Holder, __recursive__=Target)
        configured = template(_cli_parse_args=["--target.value", "9"])
        assert isinstance(configured.target, Factory)
        resolved = configured.model_resolve()
        assert isinstance(resolved.target, Target)
        assert (resolved.target.value, resolved.target.label) == (9, "retained")
        assert template().model_resolve().target.value == 5
        assert not {"rich", "docstring_parser", "yaml", "tomli_w"}.intersection(sys.modules)
        ''',
        ("rich", "docstring_parser", "yaml", "tomli_w"),
    )


@pytest.mark.parametrize("method", ["Config.model_info", "Config().info"])
@pytest.mark.parametrize("output", ["table", "string", "print"])
def test_rich_modes_require_the_extra(tmp_path: Path, method: str, output: str) -> None:
    """Every Rich output mode names the extra when Rich is unavailable."""
    _run(
        tmp_path,
        f"""
        from confidantic import BaseConfig

        class Config(BaseConfig):
            value: int = 1

        try:
            {method}(output={output!r})
        except ImportError as error:
            assert "install confidantic[rich]" in str(error)
        else:
            raise AssertionError("missing Rich was accepted")
        """,
        ("rich",),
    )


@pytest.mark.parametrize(
    "text",
    [
        "Summary.\n\nAttributes\n----------\n@attrs",
        "Summary.\n\nAttributes:\n    @attrs",
    ],
)
def test_active_docstring_marker_requires_the_extra(tmp_path: Path, text: str) -> None:
    """Valid generation requests require the parser at class creation."""
    _run(
        tmp_path,
        f"""
        from confidantic import BaseConfig
        try:
            class Config(BaseConfig):
                __doc__ = {text!r}
                value: int = 1
        except ImportError as error:
            assert "install confidantic[docstrings]" in str(error)
        else:
            raise AssertionError("missing docstring-parser was accepted")
        """,
        ("docstring_parser",),
    )


@pytest.mark.parametrize(
    "text, disabled",
    [
        ("Summary mentions @attrs in prose.", False),
        ("Summary.\n\nExamples:\n    @attrs", False),
        ("Summary.\n\nExamples\n--------\n@attrs", False),
        ("Summary.\n\n```python\n@attrs\n```", False),
        ("Summary.\n\nAttributes:\n    value:\n        @attrs", False),
        ("Summary.\n\nAttributes:\n    @attrs", True),
    ],
)
def test_ignored_or_disabled_markers_do_not_import_parser(
    tmp_path: Path, text: str, disabled: bool
) -> None:
    """Literal markers and explicit opt-outs work without the docstrings extra."""
    _run(
        tmp_path,
        f"""
        from confidantic import BaseConfig, ConfigModelDict

        class Config(BaseConfig):
            __doc__ = {text!r}
            model_config = ConfigModelDict(docstring_set_attributes_section={not disabled!r})
            value: int = 1

        assert Config.__doc__ == {text!r}
        assert "docstring_parser" not in sys.modules
        """,
        ("docstring_parser",),
    )


@pytest.mark.parametrize(
    "text, style",
    [
        ("Summary.\n\n@attrs", None),
        ("Attributes:\n    @attrs\n    @attrs:", None),
        ("Attributes\n---\n@attrs", None),
        ("Attributes:\n    @attrs", "numpy"),
    ],
)
def test_invalid_marker_precedes_missing_parser(
    tmp_path: Path, text: str, style: str | None
) -> None:
    """Structural errors remain ValueError even when the parser is missing."""
    _run(
        tmp_path,
        f"""
        from confidantic import BaseConfig, ConfigModelDict
        try:
            class Config(BaseConfig):
                __doc__ = {text!r}
                model_config = ConfigModelDict(docstring_style={style!r})
                value: int = 1
        except ValueError as error:
            assert "Config:" in str(error)
        else:
            raise AssertionError("invalid insertion request was accepted")
        assert "docstring_parser" not in sys.modules
        """,
        ("docstring_parser",),
    )


@pytest.mark.parametrize("import_error", [False, True])
@pytest.mark.parametrize(
    "module, expression",
    [
        ("rich", "Config.model_info()"),
        ("yaml", "Config().model_dump_yaml()"),
        ("tomli_w", "Config().model_dump_toml()"),
        (
            "docstring_parser",
            "type('Documented', (Config,), {'__doc__': 'Summary.\\n\\nAttributes:\\n    @attrs'})",
        ),
    ],
)
def test_dependency_internal_import_errors_are_preserved(
    tmp_path: Path, module: str, expression: str, import_error: bool
) -> None:
    """Broken installed packages are not reported as missing Confidantic extras."""
    _run(
        tmp_path,
        f"""
        from confidantic import BaseConfig

        class Config(BaseConfig):
            value: int = 1

        try:
            {expression}
        except ImportError as error:
            assert "install confidantic[" not in str(error)
            if {import_error!r}:
                assert str(error) == "broken optional package"
            else:
                assert error.name == "missing_internal_dependency"
        else:
            raise AssertionError("broken dependency was accepted")
        """,
        (module,),
        missing_name="missing_internal_dependency",
        import_error=import_error,
    )
