"""Shared helpers for tests that require an isolated Python interpreter."""

import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent


def run_python(
    script: str | Path,
    directory: Path,
    *,
    args: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute code or a script file and report captured output on failure.

    String inputs are dedented and executed with ``-c``; Path inputs name script
    files, preserving source inspection for attribute-docstring tests. Each
    invocation has a timeout and uses the test's isolated working directory.
    """
    command = [str(script)] if isinstance(script, Path) else ["-c", dedent(script)]
    result = subprocess.run(
        [sys.executable, *command, *args],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result
