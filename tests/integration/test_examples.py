"""Smoke tests for the runnable example scripts."""

import os
import subprocess
import sys
from ast import literal_eval
from pathlib import Path
from textwrap import dedent

import pytest

from tests.helpers import run_python

EXAMPLES_DIRECTORY = Path(__file__).parents[2] / "examples"


@pytest.fixture
def quickstart_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy the tutorial into an empty directory without ambient APP_ inputs."""
    for name in tuple(os.environ):
        if name.upper().startswith("APP_"):
            monkeypatch.delenv(name)
    (tmp_path / "app.py").write_text(
        (EXAMPLES_DIRECTORY / "quickstart.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("dotenv", "environment", "arguments", "expected"),
    [
        ("", {}, [], {"name": "orders", "retries": 3}),
        (
            "APP_NAME=warehouse\nAPP_RETRIES=4\n",
            {},
            [],
            {"name": "warehouse", "retries": 4},
        ),
        (
            "",
            {"APP_NAME": "shipping", "APP_RETRIES": "6"},
            [],
            {"name": "shipping", "retries": 6},
        ),
        (
            "APP_NAME=warehouse\nAPP_RETRIES=4\n",
            {"APP_NAME": "shipping", "APP_RETRIES": "6"},
            [],
            {"name": "shipping", "retries": 6},
        ),
        (
            "APP_NAME=warehouse\nAPP_RETRIES=4\n",
            {"APP_NAME": "environment", "APP_RETRIES": "8"},
            ["--name", "shipping", "--retries", "6"],
            {"name": "shipping", "retries": 6},
        ),
    ],
)
def test_quickstart_inputs(
    quickstart_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    dotenv: str,
    environment: dict[str, str],
    arguments: list[str],
    expected: dict[str, str | int],
) -> None:
    """The tutorial's CLI prints the documented source combinations."""
    if dotenv:
        (quickstart_directory / ".env").write_text(dotenv, encoding="utf-8")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    result = run_python(
        quickstart_directory / "app.py", quickstart_directory, args=arguments
    )
    assert literal_eval(result.stdout.strip()) == expected


def test_quickstart_python_overrides_and_copy(
    quickstart_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Importing is quiet; Python overrides and copies validate tutorial inputs."""
    (quickstart_directory / ".env").write_text(
        "APP_NAME=warehouse\nAPP_RETRIES=4\n", encoding="utf-8"
    )
    monkeypatch.setenv("APP_RETRIES", "6")
    result = run_python(
        """
        from app import AppConfig
        from pydantic import ValidationError

        config = AppConfig(retries=7)
        updated = config.copy(retries=5)
        print(config.model_dump())
        print(updated.model_dump())
        try:
            config.copy(retries="many")
        except ValidationError as error:
            assert error.errors()[0]["loc"] == ("retries",)
        else:
            raise AssertionError("Copy accepted an invalid retry count")
        """,
        quickstart_directory,
    )
    assert [literal_eval(line) for line in result.stdout.splitlines()] == [
        {"name": "warehouse", "retries": 7},
        {"name": "warehouse", "retries": 5},
    ]


def test_quickstart_invalid_cli_input(quickstart_directory: Path) -> None:
    """The tutorial command fails and identifies the invalid integer field."""
    result = subprocess.run(
        [sys.executable, "app.py", "--retries", "many"],
        cwd=quickstart_directory,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "retries" in result.stderr
    assert "int_parsing" in result.stderr


@pytest.mark.parametrize(
    ("filename", "arguments"),
    [
        ("basic.py", []),
        ("cli.py", ["--name", "command-line", "--number", "5"]),
        ("config_updates.py", []),
        ("configurable.py", []),
        ("context.py", []),
        ("custom_sources.py", []),
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
        ("formats.py", []),
        ("logging_config.py", []),
        ("import_directive.py", []),
        (
            "multilevel_cli.py",
            ["project", "create", "demo", "--dry-run", "true"],
        ),
        ("nested.py", []),
        ("paths.py", []),
        ("serialization.py", []),
    ],
)
def test_example_runs(
    filename: str,
    arguments: list[str],
    tmp_path: Path,
) -> None:
    """Run each guide from an isolated working directory."""
    run_python(EXAMPLES_DIRECTORY / filename, tmp_path, args=arguments)


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
    run_python(
        script,
        tmp_path,
        args=[
            str(EXAMPLES_DIRECTORY / filename),
            database_type,
            *arguments,
            "--application.database.host",
            "cli.example.com",
            "--application.database.port",
            "6543",
        ],
    )
