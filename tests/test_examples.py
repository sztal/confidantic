"""Smoke tests for the runnable example scripts."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

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
        ("logging_config.py", []),
        (
            "multilevel_cli.py",
            ["project", "create", "demo", "--dry-run", "true"],
        ),
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


@pytest.mark.parametrize(
    ("filename", "database_type", "arguments"),
    [
        ("factory_template.py", "Database", []),
        (
            "factory_dynamic_template.py",
            "ExtendedDatabase",
            ["--types.database", "__main__:ExtendedDatabase"],
        ),
    ],
)
def test_recursive_factory_template_cli(
    filename: str,
    database_type: str,
    arguments: list[str],
    tmp_path: Path,
) -> None:
    """Recursive templates expose nested CLI options for the selected target type."""
    script = dedent(
        """
        import runpy
        import sys
        from contextlib import redirect_stdout
        from io import StringIO

        path, database_type, *arguments = sys.argv[1:]
        sys.argv = [path, *arguments]
        with redirect_stdout(StringIO()):
            namespace = runpy.run_path(path, run_name="__main__")
        application = namespace["config"].application
        assert type(application) is namespace["Application"]
        assert type(application.database) is namespace[database_type]
        assert application.name == "orders"
        assert application.database.host == "cli.example.com"
        assert application.database.port == 6543
        """
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(EXAMPLES_DIRECTORY / filename),
            database_type,
            *arguments,
            "--application.database.host",
            "cli.example.com",
            "--application.database.port",
            "6543",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
