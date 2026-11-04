"""Disposable Git repositories for maintenance commands."""

import subprocess
from pathlib import Path

import pytest

from scripts import check
from scripts._repository import git


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide clean master and a local bare remote with no hooks or signing."""
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "absent-config"))
    project = tmp_path / "project"
    project.mkdir()
    git(project, "init", "-q", "--initial-branch=master")
    git(project, "config", "user.name", "Release test")
    git(project, "config", "user.email", "release@example.invalid")
    (project / "tracked").write_text("baseline\n")
    (project / ".gitignore").write_text("ignored\ndist/\n")
    (project / "CHANGELOG.md").write_text("# Changelog\n")
    (project / "changelog.d").mkdir()
    (project / "changelog.d/+pending.added.md").write_text("A pending change.\n")
    (project / "pyproject.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\n[[tool.towncrier.type]]\ndirectory = "added"\n[[tool.towncrier.type]]\ndirectory = "fixed"\n'
    )
    git(project, "add", ".")
    git(project, "commit", "-qm", "baseline")
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "clone", "--bare", str(project), str(remote)],
        check=True,
        capture_output=True,
    )
    git(project, "remote", "add", "origin", str(remote))
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def fast_checks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, str | None]]:
    """Avoid running the full suite inside preparation fixture repositories."""
    checked: list[tuple[Path, str | None]] = []
    monkeypatch.setattr(check, "source_checks", lambda directory: None)
    monkeypatch.setattr(
        check,
        "package_checks",
        lambda directory, tag=None: checked.append((directory, tag)),
    )
    return checked
