"""Validation ordering and mutations introduced by formatting hooks."""

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

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
        assert commands[2] == ["make", "check-typecheck"]
        assert commands[-1][-1] == "docs"


def test_ci_honors_the_same_typecheck_policy_after_lint() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/checks.yaml").read_text())
    job = workflow["jobs"]["checks"]
    assert job["needs"] == "lint"
    policy_step = next(
        step for step in job["steps"] if step.get("run") == "make check-typecheck"
    )
    assert not policy_step.get("continue-on-error", False)
    assert not job.get("continue-on-error", False)
    assert any(step.get("run") == "git diff --exit-code" for step in job["steps"])
