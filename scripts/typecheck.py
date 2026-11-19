"""Apply the project's type-checking level and validation policy."""

import argparse
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def settings() -> tuple[str, bool, bool]:
    """Read and validate the level, required flag, and source-only flag."""
    with PYPROJECT.open("rb") as stream:
        project = tomllib.load(stream)
    try:
        config = project["tool"]["project-checks"]
        level = config["typecheck_level"]
        required = config["require_typecheck"]
        source_only = config["typecheck_source_only"]
    except (KeyError, TypeError) as error:
        raise ValueError(
            "Missing [tool.project-checks] type-checking settings"
        ) from error
    if (
        level not in ("none", "basic", "strict")
        or not isinstance(required, bool)
        or not isinstance(source_only, bool)
    ):
        raise ValueError("Invalid [tool.project-checks] type-checking settings")
    return level, required, source_only


def mypy_args() -> list[str] | None:
    """Return level-specific mypy flags, or None when checking is disabled."""
    level, _, _ = settings()
    if level == "none":
        return None
    if level == "basic":
        return []
    return [
        "--strict",
        "--warn-unreachable",
        "--enable-error-code=ignore-without-code",
        "--enable-error-code=redundant-expr",
        "--enable-error-code=truthy-bool",
    ]


def mypy_paths() -> list[str]:
    """Return package sources and any explicitly enabled maintenance/test paths."""
    _, _, source_only = settings()
    return ["confidantic"] + ([] if source_only else ["tests", "scripts", "noxfile.py"])


def main(argv: Sequence[str] | None = None) -> None:
    """Run type checking, optionally allowing advisory failures.

    Parameters
    ----------
    argv
        Optional command-line arguments; ``--policy`` honors require_typecheck.
        By default arguments are read from the command line.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", action="store_true")
    args = parser.parse_args(argv)
    level, required, _ = settings()
    if level == "none":
        print("Type checking is disabled.")
        return
    try:
        subprocess.run(["make", "_typecheck"], cwd=PYPROJECT.parent, check=True)
    except subprocess.CalledProcessError:
        if not args.policy or required:
            raise
        print("Type checking failed (not required); continuing.", file=sys.stderr)


if __name__ == "__main__":
    main()
