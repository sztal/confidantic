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
    "optional-deps",
    "tests",
]

PYPROJECT = nox.project.load_toml()
PROJECT_NAME = PYPROJECT["project"]["name"]
SUPPORTED_PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT)
DEFAULT_PYTHON_VERSION = Path(".python-version").read_text().rstrip()


@nox.session(python=SUPPORTED_PYTHON_VERSIONS, tags=["tests"])
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.install(".[all]", "--group", "dev")

    if session.posargs:
        session.run("pytest", *session.posargs)
        return

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
    session.install("-e", ".[all]", "--group", "docs")
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
    session.install("-e", ".[all]", "--group", "docs")
    session.run(
        "zensical",
        "serve",
        "--open",
        *session.posargs,
    )


@nox.session(name="optional-deps", python=DEFAULT_PYTHON_VERSION, tags=["checks"])
def optional_dependencies(session: nox.Session) -> None:
    """Check the built wheel with each optional dependency in an isolated install."""
    session.install("uv>=0.8.6")
    session.run("python", "scripts/check_optional_dependencies.py")


if __name__ == "__main__":
    nox.main()
