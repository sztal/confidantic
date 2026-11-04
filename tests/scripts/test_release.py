"""Release preflight and recovery checks in disposable repositories."""

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts import release


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., str]:
    """Provide a clean repository without hooks, signing, or a remote."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "absent-config"))

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init", "-q", "--initial-branch=main")
    git("config", "user.name", "Release test")
    git("config", "user.email", "release@example.invalid")
    Path("tracked").write_text("baseline")
    Path(".gitignore").write_text("ignored\n")
    git("add", ".")
    git("commit", "-qm", "baseline")
    return git


@pytest.mark.parametrize(
    "state", ["clean", "staged", "unstaged", "untracked", "ignored"]
)
def test_release_preflight(repository: Callable[..., str], state: str) -> None:
    """Only clean or ignored-only working trees pass preflight."""
    if state in {"staged", "unstaged"}:
        Path("tracked").write_text("changed")
        if state == "staged":
            repository("add", "tracked")
    elif state in {"untracked", "ignored"}:
        Path(state).write_text("data")
    if state in {"clean", "ignored"}:
        release.check_repository()
    else:
        with pytest.raises(RuntimeError, match="clean working tree"):
            release.check_repository()


@pytest.mark.parametrize("state", ["detached", "branch", "tag"])
def test_release_rejects_existing_state(
    repository: Callable[..., str], state: str
) -> None:
    """Preflight failures preserve existing references and checkout."""
    if state == "detached":
        repository("checkout", "--detach")
    elif state == "branch":
        repository("branch", "release/9.9.9")
    else:
        repository("tag", "v9.9.9")
    refs = repository("show-ref")
    head = repository("rev-parse", "HEAD")
    with pytest.raises(RuntimeError):
        release.main(["--dry-run", "9.9.9"])
    assert repository("show-ref") == refs
    assert repository("rev-parse", "HEAD") == head


@pytest.fixture
def release_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Towncrier and guard against accidental publication."""
    monkeypatch.setattr(release, "get_release_notes", lambda version: "Release notes")
    monkeypatch.setattr(
        release, "update_changelog", lambda version: Path("tracked").write_text(version)
    )

    def no_publish(*args: Any) -> None:
        pytest.fail("Unexpected publication")

    monkeypatch.setattr(release, "create_release", no_publish)


def test_release_dry_run_restores_repository(
    repository: Callable[..., str], release_steps: None
) -> None:
    """A completed dry run removes only its own branch and tag."""
    refs = repository("show-ref")
    assert release.main(["--dry-run", "9.9.9"]) == 0
    assert repository("show-ref") == refs
    assert repository("branch", "--show-current") == "main"
    assert Path("tracked").read_text() == "baseline"
    assert not repository("status", "--porcelain")


@pytest.mark.parametrize(
    "phase", ["create", "notes", "changelog", "commit", "tag", "push", "publish"]
)
def test_release_failure_preserves_recovery_state(
    repository: Callable[..., str],
    release_steps: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    phase: str,
) -> None:
    """Failures retain newly created work and never delete existing branches."""
    call = subprocess.check_call
    failure = RuntimeError("injected failure")

    def fail(*args: Any, **kwargs: Any) -> None:
        raise failure

    def checked_call(command: list[str], **kwargs: Any) -> int:
        if (phase == "create" and command[1:3] == ["switch", "--create"]) or (
            phase == "commit" and command[1] == "commit"
        ):
            raise failure
        if command[1] == "push":
            if phase == "push":
                raise failure
            assert phase == "publish"
            return 0
        return call(command, **kwargs)

    monkeypatch.setattr(subprocess, "check_call", checked_call)
    for key, attribute in {
        "notes": "get_release_notes",
        "changelog": "update_changelog",
        "tag": "create_release_tag",
        "publish": "create_release",
    }.items():
        if phase == key:
            monkeypatch.setattr(release, attribute, fail)
    with pytest.raises(RuntimeError) as raised:
        release.main(["9.9.9"])
    assert raised.value is failure
    if phase == "create":
        assert repository("branch", "--show-current") == "main"
        assert not repository("branch", "--list", "release/9.9.9")
    else:
        assert repository("branch", "--show-current") == "release/9.9.9"
        assert "retained branch 'release/9.9.9'" in capsys.readouterr().err
        if phase in {"push", "publish"}:
            assert repository("tag", "--list", "v9.9.9") == "v9.9.9"
        if phase in {"commit", "tag", "push", "publish"}:
            assert Path("tracked").read_text() == "9.9.9"


def test_successful_publication_keeps_tag_and_finishes_on_main(
    repository: Callable[..., str],
    release_steps: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful publication preserves ordering without contacting a remote."""
    calls: list[tuple[str, ...]] = []
    original_call = subprocess.check_call

    def checked_call(command: list[str], **kwargs: Any) -> int:
        calls.append(tuple(command))
        if command[1] in {"push", "fetch", "pull"}:
            return 0
        return original_call(command, **kwargs)

    def publish(tag: str, notes: str) -> None:
        assert tag == "v9.9.9" and notes == "Release notes"
        assert calls[-1][1] == "push"
        calls.append(("publish", tag))

    monkeypatch.setattr(subprocess, "check_call", checked_call)
    monkeypatch.setattr(release, "create_release", publish)
    assert release.main(["9.9.9"]) == 0
    assert repository("branch", "--show-current") == "main"
    assert not repository("branch", "--list", "release/9.9.9")
    assert repository("tag", "--list", "v9.9.9") == "v9.9.9"
    assert calls[-3:] == [
        ("git", "fetch", "origin", "main"),
        ("git", "switch", "main"),
        ("git", "pull", "--ff-only", "origin", "main"),
    ]
