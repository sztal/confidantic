"""Shared Git safeguards for local merge and release preparation."""

import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkdtemp

from packaging.version import Version

MASTER = "refs/heads/master"
TAG_PATTERN = re.compile(
    r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:(a|b|rc)(0|[1-9][0-9]*))?"
)


def git(directory: Path, *args: str) -> str:
    """Run Git in a repository and return stripped standard output."""
    return subprocess.check_output(["git", *args], cwd=directory, text=True).strip()


def tag_version(tag: str) -> Version:
    """Parse a canonical release tag, rejecting development and local versions."""
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError("Expected vX.Y.Z or vX.Y.Z followed by aN, bN, or rcN")
    return Version(tag[1:])


def clean(directory: Path) -> None:
    """Reject staged, unstaged, and untracked work; allow ignored files."""
    if git(directory, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("Preparation requires a clean working tree and index")


def ancestor(directory: Path, older: str, newer: str) -> bool:
    """Return whether an existing commit is an ancestor of another commit."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], cwd=directory
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Missing Git history; fetch origin and tags first")
    return result.returncode == 0


def preflight(directory: Path) -> tuple[str, str]:
    """Require clean master containing current remote master without fetching."""
    clean(directory)
    if git(directory, "symbolic-ref", "--quiet", "HEAD") != MASTER:
        raise RuntimeError("Preparation requires the master branch")
    head = git(directory, "rev-parse", MASTER)
    remote = git(directory, "ls-remote", "--exit-code", "origin", MASTER).split()[0]
    if not ancestor(directory, remote, head):
        raise RuntimeError("Local master is behind or diverged from origin/master")
    return head, remote


def unchanged(directory: Path, head: str, remote: str) -> None:
    """Refuse installation when local or remote master changed during validation."""
    if preflight(directory) != (head, remote):
        raise RuntimeError("Master changed during validation; prepare again")


@contextmanager
def isolated(directory: Path, head: str) -> Iterator[Path]:
    """Prepare in an independent Git checkout; retain failures for recovery.

    Independent refs keep temporary release tags out of the caller's repository,
    including during dry runs. Only successful preparations are removed.
    """
    parent = Path(mkdtemp(prefix="confidantic-prepare-"))
    checkout = parent / "checkout"
    try:
        git(
            parent,
            "clone",
            "--no-hardlinks",
            "--no-checkout",
            str(directory),
            str(checkout),
        )
        git(checkout, "checkout", "--detach", head)
        for key in ("user.name", "user.email"):
            git(checkout, "config", key, git(directory, "config", "--get", key))
        yield checkout
    except BaseException:
        print(f"Preparation failed; retained checkout at {checkout}", file=sys.stderr)
        raise
    else:
        shutil.rmtree(parent)


def advance(
    directory: Path,
    checkout: Path,
    head: str,
    remote: str,
    source: tuple[str, str] | None = None,
) -> None:
    """Import a validated commit and fast-forward the caller's clean master."""
    unchanged(directory, head, remote)
    prepared = git(checkout, "rev-parse", "HEAD")
    git(
        directory,
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        str(checkout),
        prepared,
    )
    unchanged(directory, head, remote)
    if source and git(directory, "rev-parse", source[0]) != source[1]:
        raise RuntimeError("Source branch changed during validation; prepare again")
    git(directory, "merge", "--ff-only", prepared)


def verify_tag(directory: Path, tag: str, master: str = MASTER) -> str:
    """Require an annotated release tag on master history and return its commit."""
    tag_version(tag)
    ref = f"refs/tags/{tag}"
    if git(directory, "cat-file", "-t", ref) != "tag":
        raise ValueError("Release tags must be annotated")
    header = git(directory, "cat-file", "-p", ref).partition("\n\n")[0]
    if "type commit" not in header.splitlines():
        raise ValueError("Release tag must point directly to a commit")
    commit = git(directory, "rev-parse", f"{ref}^{{commit}}")
    if not ancestor(directory, commit, master):
        raise ValueError("Release tag is not on master history")
    return commit
