# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "packaging>=24.2",
#   "towncrier>=25.8",
# ]
# ///
"""Prepare a changelog commit, publish its tag and GitHub release, and update main."""

import argparse
import subprocess
import sys
from collections.abc import Sequence

from packaging.version import Version


def create_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        description="release a new version",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do not update the origin remote and reset the local repository",
    )
    parser.add_argument("version", type=Version, help="provide the version")
    return parser


def check_repository() -> None:
    """Reject staged, unstaged, or untracked work; allow ignored files."""
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], text=True
    )
    if status:
        raise RuntimeError("Release requires a clean working tree and index")


def get_current_branch() -> str:
    """Return the current branch, rejecting detached HEAD."""
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        raise RuntimeError("Release requires an attached branch")
    result.check_returncode()
    return result.stdout.rstrip()


def get_release_notes(version: str) -> str:
    """Draft Towncrier notes, replace their first line, and add a release heading."""
    release_notes = subprocess.check_output(
        ["towncrier", "build", "--version", version, "--draft"],
        stderr=subprocess.DEVNULL,
        text=True,
    ).rstrip()
    release_notes = "".join(release_notes.splitlines(keepends=True)[1:])
    release_notes = release_notes.strip()
    return f"## Release notes\n\n{release_notes}"


def update_changelog(version: str) -> None:
    """Build the changelog with Towncrier and remove consumed fragments."""
    subprocess.check_call(["towncrier", "build", "--version", version, "--yes"])


def create_release_tag(version: str) -> str:
    """Create an annotated v-prefixed tag at HEAD and return its name."""
    release_tag = f"v{version}"
    message = f"bump version to {version}"
    # Make sure to create an annotated tag.
    subprocess.check_call(
        ["git", "tag", "--annotate", release_tag, "--message", message],
    )
    return release_tag


def create_release(release_tag: str, release_notes: str) -> None:
    """Create the GitHub release with release notes."""
    subprocess.check_call(
        ["gh", "release", "create", release_tag, "--notes", release_notes]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare and publish a release from the current clean, attached branch.

    A temporary release branch holds the Towncrier changelog commit and an
    annotated tag. Normal execution pushes that commit to origin/main and the
    tag atomically, creates the GitHub release, and finishes on updated main.
    Failed preparation or publication retains the release branch and any created
    tag for recovery; remote publication is not rolled back.

    Parameters
    ----------
    argv
        Arguments for the parser, or ``None`` to use process arguments.
        ``--dry-run`` still builds and commits the changelog and creates a local
        tag. A successful dry run deletes those temporary references and restores
        the original branch without publishing.

    Returns
    -------
    int
        Zero after successful completion. Parser, subprocess, and preflight
        errors propagate or exit instead of returning a failure code.
    """
    # Parse command-line arguments.
    parser = create_parser()
    args = parser.parse_args(argv)

    # Reject user work before staging or switching branches.
    check_repository()
    version = str(args.version)
    release_branch = f"release/{version}"
    base_branch = get_current_branch()
    release_tag = f"v{version}"
    for ref in (f"refs/heads/{release_branch}", f"refs/tags/{release_tag}"):
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", ref], check=False
        )
        if result.returncode == 0:
            raise RuntimeError(f"Release reference already exists: {ref}")
        if result.returncode != 1:
            result.check_returncode()

    # Failed creation must never trigger cleanup of an existing branch.
    subprocess.check_call(["git", "switch", "--create", release_branch])
    tag_created = False
    try:
        # Update the changelog.
        release_notes = get_release_notes(version)
        update_changelog(version)

        # Stage changes produced by the release workflow.
        subprocess.check_call(["git", "add", "--all", "."])

        # Commit changes.
        message = f"chore: prepare release {version}"
        subprocess.check_call(["git", "commit", "--no-verify", "--message", message])

        # Create the release tag.
        release_tag = create_release_tag(version)
        tag_created = True

        if not args.dry_run:
            subprocess.check_call(
                [
                    "git",
                    "push",
                    "--atomic",
                    "origin",
                    f"{release_branch}:main",
                    release_tag,
                ]
            )
            create_release(release_tag, release_notes)
    except BaseException:
        retained = f"branch {release_branch!r}"
        if tag_created:
            retained += f" and tag {release_tag!r}"
        print(f"Release failed; retained {retained} for recovery", file=sys.stderr)
        raise

    # Only a completed release may discard resources created above.
    if args.dry_run:
        subprocess.check_call(["git", "tag", "--delete", release_tag])
    subprocess.check_call(["git", "checkout", base_branch])
    subprocess.check_call(["git", "branch", "--delete", "--force", release_branch])
    if args.dry_run:
        return 0

    # Fetch all changes from the remote main branch.
    subprocess.check_call(["git", "fetch", "origin", "main"])
    # Switch to the main branch.
    subprocess.check_call(["git", "switch", "main"])
    # Pull changes from the remote main branch.
    subprocess.check_call(["git", "pull", "--ff-only", "origin", "main"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
