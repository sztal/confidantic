"""Validate release tags and explicitly dispatch trusted publishing."""

import argparse
import json
import subprocess
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts._repository import git, tag_version, verify_tag
from scripts.release import release_notes


def gh_json(*args: str) -> Any:
    """Read a JSON response from GitHub CLI without shell interpolation."""
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def dispatch(tag: str) -> None:
    """Publish an existing remote annotated tag and watch only this dispatch."""
    tag_version(tag)
    repository = gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    ref = gh_json("api", f"repos/{repository}/git/ref/tags/{tag}")["object"]
    if ref["type"] != "tag":
        raise ValueError("Remote release tag must be annotated")
    target = gh_json("api", f"repos/{repository}/git/tags/{ref['sha']}")["object"]
    if target["type"] != "commit":
        raise ValueError("Release tag must point directly to a commit")
    comparison = gh_json("api", f"repos/{repository}/compare/{target['sha']}...master")
    if comparison["status"] not in ("ahead", "identical"):
        raise ValueError("Remote release tag is not on master history")
    request = uuid.uuid4().hex
    title = f"Publish {tag} [{request}]"
    subprocess.run(
        [
            "gh",
            "workflow",
            "run",
            "release.yaml",
            "--ref",
            "master",
            "-f",
            f"tag={tag}",
            "-f",
            f"request_id={request}",
        ],
        check=True,
    )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        runs = gh_json(
            "run",
            "list",
            "--workflow",
            "release.yaml",
            "--event",
            "workflow_dispatch",
            "--limit",
            "100",
            "--json",
            "databaseId,displayTitle",
        )
        for run in runs:
            if run["displayTitle"] == title:
                run_id = str(run["databaseId"])
                print(
                    f"https://github.com/{repository}/actions/runs/{run_id}", flush=True
                )
                subprocess.run(
                    ["gh", "run", "watch", run_id, "--exit-status"], check=True
                )
                return
        time.sleep(2)
    raise RuntimeError(
        f"Dispatch not observed within 120 seconds; inspect Actions for {title} before retrying"
    )


def notes_for_tag(project: Path, tag: str) -> str:
    """Get candidate preview notes or the final tagged changelog section."""
    version = tag_version(tag)
    if version.is_prerelease:
        return release_notes(project, str(version))
    changelog = git(project, "show", f"refs/tags/{tag}:CHANGELOG.md")
    heading = f"## [{version}]"
    lines = changelog.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(heading):
            end = next(
                (n for n in range(index + 1, len(lines)) if lines[n].startswith("## ")),
                len(lines),
            )
            return "\n".join(lines[index:end]).strip() + "\n"
    raise ValueError(f"Changelog has no section for {version}")


def main(argv: Sequence[str] | None = None) -> None:
    """Dispatch publication, verify a CI tag, or render notes from its checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--notes-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    version = tag_version(args.tag)
    if args.verify:
        project = Path.cwd()
        commit = verify_tag(project, args.tag, "refs/remotes/origin/master")
        remote = git(
            project, "ls-remote", "--exit-code", "origin", f"refs/tags/{args.tag}"
        ).split()[0]
        if remote != git(project, "rev-parse", f"refs/tags/{args.tag}"):
            raise ValueError("Remote tag changed; fetch and validate again")
        result = f"commit={commit}\ntag={args.tag}\nindex={'testpypi' if version.is_prerelease else 'pypi'}\nprerelease={str(version.is_prerelease).lower()}\n"
        if args.output:
            with args.output.open("a") as output:
                output.write(result)
        print(result, end="")
    elif args.notes_file:
        if verify_tag(Path.cwd(), args.tag, "HEAD") != git(
            Path.cwd(), "rev-parse", "HEAD"
        ):
            raise ValueError("Notes must be rendered at the tagged commit")
        args.notes_file.write_text(notes_for_tag(Path.cwd(), args.tag))
    else:
        dispatch(args.tag)


if __name__ == "__main__":
    main()
