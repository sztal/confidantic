"""Local release preparation, tag policy, and recovery behavior."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import check, release
from scripts._repository import clean, git, tag_version, verify_tag


@pytest.fixture
def towncrier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate Towncrier while retaining real Git commits and tags."""
    original = subprocess.run

    def run(command: list[str], **kwargs: Any) -> Any:
        if command[:5] == ["uv", "run", "--group", "release", "towncrier"]:
            project = Path(kwargs["cwd"])
            version = command[command.index("--version") + 1]
            (project / "CHANGELOG.md").write_text(
                f"# Changelog\n\n## [{version}]\n\nA change.\n"
            )
            for fragment in (project / "changelog.d").glob("*.md"):
                fragment.unlink()
            return subprocess.CompletedProcess(command, 0)
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(
        release, "release_notes", lambda project, version: "Candidate notes"
    )


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3a1", "1.2.3b2", "1.2.3rc1"])
@pytest.mark.parametrize("dry", [False, True])
def test_local_preparation(
    repository: Path, fast_checks: list[Any], towncrier: None, version: str, dry: bool
) -> None:
    """Candidates preserve notes, finals consume them, and rehearsals change no refs."""
    original_refs = git(repository, "show-ref")
    original_remote = git(repository, "ls-remote", "origin")
    branch = f"v{version}"
    git(repository, "branch", branch)  # Branch/tag collisions must be unambiguous.
    before = git(repository, "show-ref")
    release.main((["--dry-run"] if dry else []) + [version])
    clean(repository)
    assert git(repository, "ls-remote", "origin") == original_remote
    assert git(repository, "branch", "--show-current") == "master"
    if dry:
        assert git(repository, "show-ref") == before
        assert (repository / "changelog.d/+pending.added.md").exists()
    else:
        assert git(repository, "cat-file", "-t", f"refs/tags/{branch}") == "tag"
        assert verify_tag(repository, branch) == git(repository, "rev-parse", "HEAD")
        assert (repository / "changelog.d/+pending.added.md").exists() == tag_version(
            branch
        ).is_prerelease
    assert original_refs
    assert fast_checks[0][1] == branch
    assert not fast_checks[0][0].exists()


@pytest.mark.parametrize(
    "state", ["staged", "unstaged", "untracked", "branch", "detached"]
)
def test_preflight_preserves_user_work(repository: Path, state: str) -> None:
    if state in ("staged", "unstaged"):
        (repository / "tracked").write_text("user work")
        if state == "staged":
            git(repository, "add", "tracked")
    elif state == "untracked":
        (repository / "new").write_text("user work")
    elif state == "branch":
        git(repository, "switch", "-c", "feature")
    else:
        git(repository, "checkout", "--detach")
    before = git(repository, "status", "--porcelain"), git(repository, "show-ref")
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        release.main(["1.0.0"])
    assert (
        git(repository, "status", "--porcelain"),
        git(repository, "show-ref"),
    ) == before


@pytest.mark.parametrize(
    "tag",
    [
        "1.2.3",
        "v1.2",
        "v01.2.3",
        "v1.2.3.dev1",
        "v1.2.3+local",
        "v1.2.3.post1",
        "v1.2.3rc01",
        "v1.2.3\n",
    ],
)
def test_invalid_tags(tag: str) -> None:
    with pytest.raises(ValueError):
        tag_version(tag)


@pytest.mark.parametrize("remote", [False, True])
def test_existing_and_older_versions(repository: Path, remote: bool) -> None:
    git(repository, "tag", "-a", "v2.0.0rc1", "-m", "Candidate")
    if remote:
        git(repository, "push", "origin", "refs/tags/v2.0.0rc1")
        git(repository, "tag", "-d", "v2.0.0rc1")
    for version in ("2.0.0rc1", "1.0.0"):
        with pytest.raises(ValueError):
            release.available_version(repository, f"v{version}")
    release.available_version(repository, "v2.0.0")


def test_failure_retains_isolation(
    repository: Path,
    fast_checks: list[Any],
    towncrier: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = git(repository, "show-ref")
    retained: list[Path] = []

    def fail(directory: Path, tag: str | None = None) -> None:
        retained.append(directory)
        raise RuntimeError("Failed build")

    monkeypatch.setattr(check, "package_checks", fail)
    with pytest.raises(RuntimeError, match="Failed build"):
        release.main(["--dry-run", "1.0.0"])
    assert git(repository, "show-ref") == before
    assert retained[0].exists()
    assert "retained checkout" in capsys.readouterr().err
    assert git(retained[0], "tag", "--list") == "v1.0.0"
    clean(repository)


def test_lightweight_and_off_master_tags(repository: Path) -> None:
    git(repository, "tag", "v1.0.0")
    with pytest.raises(ValueError, match="annotated"):
        verify_tag(repository, "v1.0.0")
    git(repository, "switch", "-c", "other")
    (repository / "other").write_text("feature")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Other")
    git(repository, "tag", "-a", "v2.0.0", "-m", "Other")
    with pytest.raises(ValueError, match="master history"):
        verify_tag(repository, "v2.0.0")


@pytest.mark.parametrize("existing", ["v1.2", "1.2.0", "v01.2.0"])
def test_legacy_tag_aliases_cannot_reuse_a_version(
    repository: Path, existing: str
) -> None:
    git(repository, "tag", "-a", existing, "-m", "Legacy release")
    with pytest.raises(ValueError, match="newer"):
        release.available_version(repository, "v1.2.0")


def test_remote_master_must_be_contained(repository: Path, tmp_path: Path) -> None:
    from scripts._repository import preflight

    remote = tmp_path / "remote.git"
    other = tmp_path / "other"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.name", "Other contributor")
    git(other, "config", "user.email", "other@example.invalid")
    git(other, "commit", "--allow-empty", "-qm", "Remote update")
    git(other, "push", "origin", "master")
    git(repository, "fetch", "origin", "master")
    with pytest.raises(RuntimeError, match="behind or diverged"):
        preflight(repository)
    git(repository, "commit", "--allow-empty", "-qm", "Diverged update")
    with pytest.raises(RuntimeError, match="behind or diverged"):
        preflight(repository)
