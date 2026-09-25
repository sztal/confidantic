"""Import-time package defaults controlled through the process environment."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

_ENVIRONMENT_VARIABLE = "CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS"


@pytest.mark.parametrize("notebook", [False, True])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("true", True),
        ("YES", True),
        ("1", True),
        ("on", True),
        ("false", False),
        ("NO", False),
        ("0", False),
        ("off", False),
    ],
)
def test_attribute_docstring_default(
    tmp_path: Path, notebook: bool, value: str | None, expected: bool | None
) -> None:
    """Environment overrides runtime detection; explicit model settings win."""
    environment = dict(os.environ)
    environment.pop(_ENVIRONMENT_VARIABLE, None)
    if value is not None:
        environment[_ENVIRONMENT_VARIABLE] = value
    expected = not notebook if expected is None else expected
    # A dotenv file is not a source for package-level defaults.
    (tmp_path / ".env").write_text(f"{_ENVIRONMENT_VARIABLE}={not expected}\n")
    script = f'''
        import os
        import sys
        from types import ModuleType
        sys.modules["IPython"] = ModuleType("IPython")
        if {notebook!r}:
            sys.modules["ipykernel"] = ModuleType("ipykernel")
        from confidantic import BaseConfig, ConfigModelDict
        from pydantic import Field
        assert BaseConfig.model_config["use_attribute_docstrings"] is {expected!r}
        os.environ["{_ENVIRONMENT_VARIABLE}"] = str({not expected!r})
        class Inherited(BaseConfig):
            value: int = Field(1, description="Explicit description")
        class Explicit(BaseConfig):
            model_config = ConfigModelDict(use_attribute_docstrings={not expected!r})
        assert Inherited.model_config["use_attribute_docstrings"] is {expected!r}
        assert Explicit.model_config["use_attribute_docstrings"] is {not expected!r}
        assert Inherited.model_fields["value"].description == "Explicit description"
    '''
    result = subprocess.run(
        [sys.executable, "-c", dedent(script)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", ["", "maybe", "2"])
def test_invalid_attribute_docstring_default(tmp_path: Path, value: str) -> None:
    """Invalid package settings fail clearly during import with a chained cause."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent("""
            from pydantic import ValidationError
            try:
                import confidantic
            except ValueError as error:
                assert "CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS" in str(error)
                assert isinstance(error.__cause__, ValidationError)
            else:
                raise AssertionError("Invalid package default was accepted")
        """),
        ],
        cwd=tmp_path,
        env={**os.environ, _ENVIRONMENT_VARIABLE: value},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
