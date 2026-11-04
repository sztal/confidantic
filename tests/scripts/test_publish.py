"""Explicit publishing dispatch and event/validation boundaries."""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from scripts import publish
from scripts._repository import git


@pytest.mark.parametrize("failure", [None, "lightweight", "outside", "workflow"])
def test_dispatch_is_explicit_and_tracks_its_run(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(publish.uuid, "uuid4", lambda: SimpleNamespace(hex="unique"))

    def response(*args: str) -> Any:
        if args[0] == "repo":
            return {"nameWithOwner": "owner/package"}
        if args[0] == "run":
            return [
                {"databaseId": 1, "displayTitle": "Publish v1.2.3 [other]"},
                {"databaseId": 2, "displayTitle": "Publish v1.2.3 [unique]"},
            ]
        if "/git/ref/" in args[1]:
            return {
                "object": {
                    "type": "commit" if failure == "lightweight" else "tag",
                    "sha": "tag-object",
                }
            }
        if "/git/tags/" in args[1]:
            return {"object": {"type": "commit", "sha": "commit"}}
        return {"status": "diverged" if failure == "outside" else "ahead"}

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[1:3] == ["run", "watch"] and failure == "workflow":
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "gh_json", response)
    monkeypatch.setattr(publish.subprocess, "run", run)
    if failure:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            publish.dispatch("v1.2.3")
    else:
        publish.dispatch("v1.2.3")
    if failure in ("lightweight", "outside"):
        assert commands == []
    else:
        assert commands[0] == [
            "gh",
            "workflow",
            "run",
            "release.yaml",
            "--ref",
            "master",
            "-f",
            "tag=v1.2.3",
            "-f",
            "request_id=unique",
        ]
        assert commands[-1] == ["gh", "run", "watch", "2", "--exit-status"]


@pytest.mark.parametrize(
    "tag,index",
    [("v1.2.3", "pypi"), ("v1.2.3rc1", "testpypi"), ("v1.2.3a1", "testpypi")],
)
def test_remote_tag_verification_and_routing(
    repository: Path, tmp_path: Path, tag: str, index: str
) -> None:
    git(repository, "tag", "-a", tag, "-m", "Release")
    git(repository, "push", "origin", f"refs/tags/{tag}")
    git(repository, "fetch", "origin", "master")
    output = tmp_path / "output"
    publish.main([tag, "--verify", "--output", str(output)])
    assert f"index={index}\n" in output.read_text()
    assert f"commit={git(repository, 'rev-parse', 'HEAD')}\n" in output.read_text()


def test_final_notes_come_from_tagged_changelog(repository: Path) -> None:
    (repository / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.2.3](link) - date\n\nFinal notes.\n\n## [1.2.2]\nOld notes.\n"
    )
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Release notes")
    git(repository, "tag", "-a", "v1.2.3", "-m", "Release")
    result = publish.notes_for_tag(repository, "v1.2.3")
    assert "Final notes." in result and "Old notes." not in result


def test_workflow_publication_requires_dispatch_and_validation() -> None:
    root = Path(__file__).resolve().parents[2]
    release = yaml.safe_load((root / ".github/workflows/release.yaml").read_text())
    checks = yaml.safe_load((root / ".github/workflows/checks.yaml").read_text())
    for name in ("publish-pypi", "publish-testpypi"):
        job = release["jobs"][name]
        assert "github.event_name == 'workflow_dispatch'" in job["if"]
        assert "github.ref == 'refs/heads/master'" in job["if"]
        assert "validation" in job["needs"]
        assert job["permissions"] == {"id-token": "write"}
        assert job["steps"][0]["with"]["name"] == "python-package-distributions"
    for name in ("tests", "checks", "distributions"):
        assert checks["jobs"][name]["needs"] == "lint"
    assert (
        "needs.validation.result == 'success'"
        in release["jobs"]["github-release"]["if"]
    )
    assert (
        "needs.publish-pypi.result == 'success'"
        in release["jobs"]["github-release"]["if"]
    )
