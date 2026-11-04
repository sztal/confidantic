"""Prepare a checked, annotated release tag on local master without publishing."""

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path

from packaging.version import InvalidVersion, Version

from scripts import check
from scripts._repository import (
    advance,
    clean,
    git,
    isolated,
    preflight,
    tag_version,
    unchanged,
)


def available_version(project: Path, tag: str) -> None:
    """Reject existing tags and versions that do not advance local or remote tags."""
    version = tag_version(tag)
    tags = set(git(project, "tag", "--list").splitlines())
    for line in git(project, "ls-remote", "--tags", "--refs", "origin").splitlines():
        tags.add(line.split()[1].removeprefix("refs/tags/"))
    for existing in tags:
        if existing == tag:
            raise ValueError(f"Release tag already exists: {tag}")
        try:
            previous = Version(existing.removeprefix("v"))
        except InvalidVersion:
            continue
        if previous >= version:
            raise ValueError(f"Release must be newer than {existing}")


def release_notes(project: Path, version: str) -> str:
    """Render pending Towncrier notes without editing tracked files."""
    return subprocess.check_output(
        [
            "uv",
            "run",
            "--locked",
            "--group",
            "release",
            "towncrier",
            "build",
            "--version",
            version,
            "--draft",
        ],
        cwd=project,
        text=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare a local release or a completely isolated rehearsal.

    Parameters
    ----------
    argv
        Canonical version without ``v``, optionally ``--notes`` for a preview or
        ``--dry-run`` for validation without changing caller refs or files.

    Returns
    -------
    int
        Zero after successful preparation. Failures retain the isolated checkout
        for inspection and propagate without pushing or publishing.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--notes", action="store_true")
    args = parser.parse_args(argv)
    tag = f"v{args.version}"
    version = tag_version(tag)
    project = Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    if args.notes:
        print(release_notes(project, str(version)))
        return 0
    head, remote = preflight(project)
    available_version(project, tag)
    with isolated(project, head) as checkout:
        if version.is_prerelease:
            print(release_notes(checkout, str(version)))
        else:
            subprocess.run(
                [
                    "uv",
                    "run",
                    "--group",
                    "release",
                    "towncrier",
                    "build",
                    "--version",
                    str(version),
                    "--yes",
                ],
                cwd=checkout,
                check=True,
            )
            git(checkout, "add", "--all", "--", "CHANGELOG.md", "changelog.d")
        tree = git(checkout, "write-tree")
        check.source_checks(checkout)
        if git(checkout, "write-tree") != tree or git(checkout, "diff", "--name-only"):
            raise RuntimeError("Checks modified the prepared release")
        if not version.is_prerelease:
            git(
                checkout,
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                f"chore: prepare release {version}",
            )
        clean(checkout)
        git(checkout, "tag", "--annotate", tag, "--message", f"Release {version}")
        check.package_checks(checkout, tag)
        clean(checkout)
        unchanged(project, head, remote)
        available_version(project, tag)
        if not args.dry_run:
            advance(project, checkout, head, remote)
            git(
                project,
                "fetch",
                "--no-write-fetch-head",
                "--no-tags",
                str(checkout),
                f"refs/tags/{tag}:refs/tags/{tag}",
            )
    if args.dry_run:
        print("Release rehearsal passed; caller files and refs unchanged")
    else:
        print(
            f"Prepared {tag} locally. To push explicitly:\n"
            f"git push --atomic origin refs/heads/master:refs/heads/master refs/tags/{tag}:refs/tags/{tag}\n"
            f"Then publish explicitly: make publish TAG={tag}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
