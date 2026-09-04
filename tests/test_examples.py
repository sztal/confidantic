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
        ("configurable.py", []),
        ("context.py", []),
        (
            "delimited.py",
            [
                "--ports",
                "[8000, 9000]",
                "--features",
                "api",
                "--features",
                "worker",
                "--options",
                "retries=3,mode=debug",
            ],
        ),
        ("directive_annotations.py", []),
        ("env_files.py", []),
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


def test_factory_gated_help_includes_generated_options() -> None:
    """The selected factory's constructor fields appear in final CLI help."""
    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIRECTORY / "factory_gated.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--estimator.window" in result.stdout
    assert "--estimator.center" in result.stdout


def test_factory_gated_router_help_includes_type_selector() -> None:
    """The routing CLI exposes the importable implementation type."""
    result = subprocess.run(
        [
            sys.executable,
            str(EXAMPLES_DIRECTORY / "factory_gated.py"),
            "--help",
            "--help.types",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--types.estimator" in result.stdout


def test_factory_gated_routes_imported_target_subclass() -> None:
    """An imported target subclass receives its generated CLI options."""
    result = subprocess.run(
        [
            sys.executable,
            str(EXAMPLES_DIRECTORY / "factory_gated.py"),
            "--types.estimator",
            "__main__:ExponentialMovingAverage",
            "--estimator.decay",
            "0.85",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ExponentialMovingAverage" in result.stdout
    assert "decay=0.85" in result.stdout
