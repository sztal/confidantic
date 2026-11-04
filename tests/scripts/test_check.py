"""Validation ordering and mutations introduced by formatting hooks."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import check


@pytest.mark.parametrize("mutate", [False, True])
def test_lint_precedes_tests_and_changes_stop_validation(
    repository: Path, monkeypatch: pytest.MonkeyPatch, mutate: bool
) -> None:
    commands: list[list[str]] = []
    run = subprocess.run
    (repository / "tracked").write_text("Existing user change")

    def execute(command: list[str], **kwargs: Any) -> Any:
        if command[0] == "git":
            return run(command, **kwargs)
        commands.append(command)
        if mutate:
            (repository / "tracked").write_text("Formatted change")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check.subprocess, "run", execute)
    if mutate:
        with pytest.raises(RuntimeError, match="modified tracked files"):
            check.source_checks(repository)
        assert len(commands) == 1
    else:
        check.source_checks(repository)
        assert commands[0][-1] == "lint"
        assert commands[1] == ["uv", "run", "pytest"]
        assert commands[-1][-1] == "docs"
