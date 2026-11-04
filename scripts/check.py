"""Run project validation in order, with lint before tests."""

import subprocess
from pathlib import Path

from scripts._repository import git


def source_checks(directory: Path) -> None:
    """Run lint, pytest, typing, and docs; reject modifications made by checks."""
    before = (
        git(directory, "diff", "--binary"),
        git(directory, "diff", "--cached", "--binary"),
    )
    commands = (
        ["uv", "run", "noxfile.py", "-s", "lint"],
        ["uv", "run", "pytest"],
        ["uv", "run", "noxfile.py", "-s", "typecheck"],
        ["uv", "run", "noxfile.py", "-s", "docs"],
    )
    for command in commands:
        subprocess.run(command, cwd=directory, check=True)
        after = (
            git(directory, "diff", "--binary"),
            git(directory, "diff", "--cached", "--binary"),
        )
        if after != before:
            raise RuntimeError(
                "Validation modified tracked files; review changes and rerun"
            )


def package_checks(directory: Path, tag: str | None = None) -> None:
    """Build distributions once and check those exact files, optionally for a tag."""
    subprocess.run(
        ["uv", "run", "python", "-m", "scripts.distributions", "build"],
        cwd=directory,
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "release",
            "python",
            "-m",
            "scripts.distributions",
            "check",
        ]
        + (["--tag", tag] if tag else []),
        cwd=directory,
        check=True,
    )


def main() -> None:
    """Validate source, then build and validate distributions from this checkout."""
    source_checks(Path.cwd())
    package_checks(Path.cwd())


if __name__ == "__main__":
    main()
