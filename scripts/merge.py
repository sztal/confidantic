"""Merge a branch into local master with consolidated release notes."""

import argparse
import tomllib
from collections.abc import Sequence
from pathlib import Path

from scripts import check
from scripts._repository import advance, ancestor, git, isolated, preflight, unchanged


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare, validate, and optionally install a merge without pushing.

    Parameters
    ----------
    argv
        Branch name, either a notes directory or a no-notes reason, and optional
        ``--check`` to rehearse without advancing master.

    Returns
    -------
    int
        Zero on success or when the branch is already merged.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch")
    notes = parser.add_mutually_exclusive_group(required=True)
    notes.add_argument("--notes", type=Path)
    notes.add_argument("--no-notes-reason")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    project = Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    head, remote = preflight(project)
    source_ref = f"refs/heads/{args.branch}"
    source = git(project, "rev-parse", "--verify", f"{source_ref}^{{commit}}")
    if ancestor(project, source, head):
        print(f"{args.branch} is already merged into master")
        return 0
    categories = {
        entry["directory"]
        for entry in tomllib.loads((project / "pyproject.toml").read_text())["tool"][
            "towncrier"
        ]["type"]
    }
    summaries: dict[str, str] = {}
    if args.notes:
        for path in args.notes.resolve().iterdir():
            if (
                path.name not in {f"{category}.md" for category in categories}
                or not path.is_file()
            ):
                raise ValueError(f"Unexpected notes file: {path.name}")
            if content := path.read_text().strip():
                summaries[path.stem] = content + "\n"
        if not summaries:
            raise ValueError("Notes directory has no nonempty category files")
    elif not args.no_notes_reason.strip():
        raise ValueError("A no-notes reason must not be empty")

    with isolated(project, head) as checkout:
        git(checkout, "merge", "--no-ff", "--no-commit", source)
        for category, content in summaries.items():
            fragment = checkout / "changelog.d" / f"+merge-{source}.{category}.md"
            fragment.parent.mkdir(exist_ok=True)
            if fragment.exists():
                raise ValueError(f"Merge summary already exists: {fragment.name}")
            fragment.write_text(content)
            git(checkout, "add", "--", str(fragment.relative_to(checkout)))
        tree = git(checkout, "write-tree")
        check.source_checks(checkout)
        check.package_checks(checkout)
        if git(checkout, "write-tree") != tree or git(checkout, "diff", "--name-only"):
            raise RuntimeError("Checks modified the prepared merge")
        message = f"Merge {args.branch} into master"
        if args.no_notes_reason:
            message += f"\n\nNo release notes: {args.no_notes_reason.strip()}"
        git(checkout, "-c", "core.hooksPath=/dev/null", "commit", "-m", message)
        if git(project, "rev-parse", source_ref) != source:
            raise RuntimeError("Source branch changed during validation; prepare again")
        unchanged(project, head, remote)
        if not args.check:
            advance(project, checkout, head, remote, (source_ref, source))
    print(
        "Merge validated" if args.check else "Merged into local master; nothing pushed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
