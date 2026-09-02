# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "nox[uv]>=2025.2.9",
#   "uv>=0.8.6",
# ]
# ///
"""Task automation with Nox."""

import os
from pathlib import Path

import nox

nox.needs_version = ">=2025.2.9"
nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = [
    "lint",
    "typecheck",
    "docs",
    "tests",
]

PYPROJECT = nox.project.load_toml()
PROJECT_NAME = PYPROJECT["project"]["name"]
SUPPORTED_PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT)
DEFAULT_PYTHON_VERSION = Path(".python-version").read_text().rstrip()


@nox.session(python=SUPPORTED_PYTHON_VERSIONS, tags=["tests"])
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.install(".[all]", "--group", "test")
    tmp_dir = Path(session.create_tmp())

    if os.getenv("COVERAGE_FILE") is None:
        session.env["COVERAGE_FILE"] = str(tmp_dir / ".coverage")

    session.run("coverage", "erase")
    session.run(
        "coverage",
        "run",
        "-m",
        "pytest",
        *(
            session.posargs
            or (
                "--durations",
                "15",
                "-n",
                os.getenv("PYTEST_XDIST_AUTO_NUM_WORKERS") or "auto",
            )
        ),
    )
    session.run("coverage", "combine")
    session.run("coverage", "report")


@nox.session(python=DEFAULT_PYTHON_VERSION, tags=["checks"])
def lint(session: nox.Session) -> None:
    """Run pre-commit linting."""
    session.install("--group", "lint")
    session.run(
        "pre-commit",
        "run",
        "--all-files",
        *session.posargs,
        env={"FORCE_PRE_COMMIT_UV_PATCH": "1"},
    )


@nox.session(python=DEFAULT_PYTHON_VERSION, tags=["checks"])
def typecheck(session: nox.Session) -> None:
    """Typecheck Python code."""
    session.install(".", "--group", "type")
    session.run(
        "mypy",
        *(session.posargs or ("confidantic", "noxfile.py", "scripts")),
    )


@nox.session(python=DEFAULT_PYTHON_VERSION, tags=["checks"])
def docs(session: nox.Session) -> None:
    """Build the documentation."""
    session.install("-e", ".", "--group", "docs")
    session.run(
        "zensical",
        "build",
        "--clean",
        "--strict",
        *session.posargs,
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def autodocs(session: nox.Session) -> None:
    """Serve the documentation locally."""
    session.install("-e", ".", "--group", "docs")
    session.run(
        "zensical",
        "serve",
        "--open",
        *session.posargs,
    )


if __name__ == "__main__":
    nox.main()
