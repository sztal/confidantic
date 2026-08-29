"""Smoke tests for the runnable example scripts."""

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIRECTORY = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize(
    ("filename", "arguments"),
    [
        ("basic.py", []),
        ("cli.py", ["--name", "command-line", "--number", "5"]),
        ("directive_annotations.py", []),
        ("factory.py", []),
        ("factory_gated.py", []),
        ("logging_config.py", []),
        ("multilevel_cli.py", ["project", "create", "demo", "--dry-run"]),
        ("nested.py", []),
        ("serialization.py", []),
    ],
)
def test_example_runs(
    filename: str,
    arguments: list[str],
    tmp_path: Path,
) -> None:
    """Run each guide from an isolated working directory."""
    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIRECTORY / filename), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
