"""Merge preparation checks using real disposable branches."""

from pathlib import Path
from typing import Any

import pytest

from scripts import check, merge
from scripts._repository import clean, git


@pytest.fixture
def feature(repository: Path) -> str:
    git(repository, "switch", "-c", "feature")
    (repository / "feature").write_text("New behavior\n")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Feature")
    source = git(repository, "rev-parse", "HEAD")
    git(repository, "switch", "master")
    return source


@pytest.mark.parametrize("rehearse", [False, True])
@pytest.mark.parametrize("notes", [False, True])
def test_merge_notes_and_repeated_invocation(
    repository: Path,
    feature: str,
    fast_checks: list[Any],
    tmp_path: Path,
    rehearse: bool,
    notes: bool,
) -> None:
    before = git(repository, "show-ref")
    summaries = tmp_path / "notes"
    summaries.mkdir()
    (summaries / "added.md").write_text("The final feature.\n")
    args = ["feature"] + (
        ["--notes", str(summaries)]
        if notes
        else ["--no-notes-reason", "Internal refactor"]
    )
    merge.main(args + (["--check"] if rehearse else []))
    clean(repository)
    assert not git(repository, "tag", "--list")
    if rehearse:
        assert git(repository, "show-ref") == before
    else:
        assert (
            len(git(repository, "rev-list", "--parents", "-n", "1", "HEAD").split())
            == 3
        )
        assert (repository / "feature").exists()
        fragment = repository / "changelog.d" / f"+merge-{feature}.added.md"
        assert fragment.exists() == notes
        if notes:
            assert fragment.read_text() == "The final feature.\n"
        else:
            assert "No release notes: Internal refactor" in git(
                repository, "log", "-1", "--format=%B"
            )
        after = git(repository, "show-ref")
        merge.main(args)
        assert git(repository, "show-ref") == after


@pytest.mark.parametrize("change", ["source", "target", "dirty", "failure", "index"])
def test_changed_inputs_and_failed_checks(
    repository: Path,
    feature: str,
    fast_checks: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    master = git(repository, "rev-parse", "HEAD")

    def validate(directory: Path, tag: str | None = None) -> None:
        if change == "source":
            git(repository, "update-ref", "refs/heads/feature", master)
        elif change == "target":
            git(
                repository, "commit", "--allow-empty", "-qm", "Concurrent master change"
            )
        elif change == "dirty":
            (repository / "tracked").write_text("Concurrent edits")
        elif change == "index":
            (directory / "unexpected").write_text("unexpected staged content")
            git(directory, "add", ".")
        else:
            raise RuntimeError("Check failed")

    monkeypatch.setattr(check, "package_checks", validate)
    with pytest.raises(RuntimeError):
        merge.main(["feature", "--no-notes-reason", "Internal"])
    assert not (repository / "feature").exists()
    assert not list((repository / "changelog.d").glob("+merge-*"))
    if change != "target":
        assert git(repository, "rev-parse", "HEAD") == master


def test_conflict_is_isolated(
    repository: Path, feature: str, fast_checks: list[Any]
) -> None:
    (repository / "feature").write_text("Conflicting master behavior")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Conflict")
    before = git(repository, "show-ref")
    import subprocess

    with pytest.raises(subprocess.CalledProcessError):
        merge.main(["feature", "--no-notes-reason", "Internal"])
    assert git(repository, "show-ref") == before
    clean(repository)


def test_source_is_rechecked_after_import(
    repository: Path,
    feature: str,
    fast_checks: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import _repository

    master = git(repository, "rev-parse", "HEAD")
    original = _repository.git

    def change_after_fetch(directory: Path, *args: str) -> str:
        result = original(directory, *args)
        if directory == repository and args[0] == "fetch":
            original(repository, "update-ref", "refs/heads/feature", master)
        return result

    monkeypatch.setattr(_repository, "git", change_after_fetch)
    with pytest.raises(RuntimeError, match="Source branch changed"):
        merge.main(["feature", "--no-notes-reason", "Internal"])
    assert git(repository, "rev-parse", "HEAD") == master
    clean(repository)
