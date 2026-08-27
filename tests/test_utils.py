"""Tests for runtime utilities."""

import sys
from types import ModuleType

import pytest

from confidantic.utils import is_runtime_jupyterlike


def test_runtime_without_ipython_is_not_jupyterlike(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable IPython runtime uses the non-kernel fallback."""
    monkeypatch.delitem(sys.modules, "ipykernel", raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ModuleType("IPython"))

    assert is_runtime_jupyterlike() is False


@pytest.mark.parametrize(
    ("shell_name", "expected"),
    [
        ("ZMQInteractiveShell", True),
        ("TerminalInteractiveShell", False),
    ],
)
def test_runtime_classifies_ipython_shell(
    monkeypatch: pytest.MonkeyPatch,
    shell_name: str,
    expected: bool,
) -> None:
    """Only IPython's kernel shell is notebook-like."""
    monkeypatch.delitem(sys.modules, "ipykernel", raising=False)
    shell = type(shell_name, (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)

    assert is_runtime_jupyterlike() is expected
