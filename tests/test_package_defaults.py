"""Import-time package defaults."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

_ENVIRONMENT_VARIABLE = "CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS"


@pytest.mark.parametrize("notebook", [False, True])
@pytest.mark.parametrize("value", [None, "true", "false", "invalid"])
def test_attribute_docstring_default(
    tmp_path: Path, notebook: bool, value: str | None
) -> None:
    """Runtime detection sets the default and explicit model settings win."""
    environment = dict(os.environ)
    environment.pop(_ENVIRONMENT_VARIABLE, None)
    if value is not None:
        environment[_ENVIRONMENT_VARIABLE] = value
    expected = not notebook
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
