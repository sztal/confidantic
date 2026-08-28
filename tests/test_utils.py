"""Tests for runtime utilities."""

import sys
from types import ModuleType

import pendulum as pdt
import pytest

from confidantic.utils import (
    get_import_string,
    import_from_string,
    is_runtime_jupyterlike,
    parse_date,
    parse_datetime,
    parse_time,
)


def test_runtime_without_ipython_is_not_jupyterlike(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable IPython runtime uses the non-kernel fallback."""
    monkeypatch.delitem(sys.modules, "ipykernel", raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ModuleType("IPython"))

    assert is_runtime_jupyterlike() is False


def test_runtime_with_ipykernel_is_jupyterlike(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An active ipykernel module takes precedence over IPython inspection."""
    monkeypatch.setitem(sys.modules, "ipykernel", ModuleType("ipykernel"))

    assert is_runtime_jupyterlike() is True


def test_runtime_without_active_ipython_shell_is_not_jupyterlike(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An IPython module without an active shell is not notebook-like."""
    monkeypatch.delitem(sys.modules, "ipykernel", raising=False)
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: None, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)

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


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        (sys, "sys"),
        (int, "builtins:int"),
        (get_import_string, "confidantic.utils:get_import_string"),
        (object(), "builtins:object"),
    ],
)
def test_get_import_string_returns_importable_object_path(
    obj: object,
    expected: str,
) -> None:
    """Import strings identify modules, qualified objects, and instances."""
    assert get_import_string(obj) == expected


def test_import_from_string_resolves_and_validates_import() -> None:
    """Import strings resolve objects and honor an explicit type hint."""
    assert import_from_string("builtins:dict") is dict
    assert import_from_string("builtins:dict", type_hint=type) is dict


@pytest.mark.parametrize(
    "import_string",
    [
        "not-an-import-string",
        "missing_module:object",
        "builtins:missing_object",
    ],
)
def test_import_from_string_rejects_invalid_import(
    import_string: str,
) -> None:
    """Invalid module and attribute paths raise validation errors."""
    with pytest.raises(ValueError):
        import_from_string(import_string)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pdt.date(2026, 8, 28), pdt.date(2026, 8, 28)),
        ("2026-08-28", pdt.date(2026, 8, 28)),
        ("2026-08-28T12:34:56+00:00", pdt.date(2026, 8, 28)),
    ],
)
def test_parse_date(value: object, expected: pdt.Date) -> None:
    """Dates parse from native, date-only, and datetime values."""
    assert parse_date(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            pdt.datetime(2026, 8, 28, 12, 34, 56, tz="UTC"),
            pdt.datetime(2026, 8, 28, 12, 34, 56, tz="UTC"),
        ),
        (
            "2026-08-28T12:34:56+00:00",
            pdt.datetime(2026, 8, 28, 12, 34, 56, tz="UTC"),
        ),
    ],
)
def test_parse_datetime(value: object, expected: pdt.DateTime) -> None:
    """Datetimes parse from native and ISO-formatted values."""
    assert parse_datetime(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pdt.time(12, 34, 56), pdt.time(12, 34, 56)),
        ("12:34:56", pdt.time(12, 34, 56)),
        ("2026-08-28T12:34:56+00:00", pdt.time(12, 34, 56)),
    ],
)
def test_parse_time(value: object, expected: pdt.Time) -> None:
    """Times parse from native, time-only, and datetime values."""
    assert parse_time(value) == expected
