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

from scripts import typecheck as typecheck_policy

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
    """Run tests for each supported Python version in the contributor matrix.

    With positional arguments, invoke pytest directly with those arguments.
    Otherwise run pytest under coverage with xdist, combine subprocess data,
    and report coverage. Coverage uses a session temporary file unless the
    caller supplies COVERAGE_FILE.
    """
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
    """Typecheck the configured scope and level, failing on mypy errors."""
    args = typecheck_policy.mypy_args()
    if args is None:
        session.skip("Type checking is disabled.")
    session.install(".", "--group", "type")
    session.run("mypy", *args, *(session.posargs or typecheck_policy.mypy_paths()))


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
    session.run("python", "scripts/check_optional_dependencies.py", *session.posargs)


if __name__ == "__main__":
    nox.main()
