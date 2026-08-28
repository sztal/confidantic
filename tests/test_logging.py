"""Tests for the logging configuration base class."""

import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from confidantic import BaseLogging, SettingsConfigDict


class AppLogging(BaseLogging):
    """Logging configuration with an application-owned environment prefix."""

    model_config = SettingsConfigDict(env_prefix="APP_LOG_")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("debug", "DEBUG"),
        ("warn", "WARNING"),
        ("fatal", "CRITICAL"),
    ],
)
def test_log_levels_are_canonicalized(value: str, expected: str) -> None:
    """Standard level names and aliases normalize to canonical uppercase names."""
    assert BaseLogging.model_validate({"level": value}).level == expected


def test_log_levels_reject_unknown_names() -> None:
    """Unsupported textual levels are rejected during validation."""
    with pytest.raises(ValidationError):
        BaseLogging.model_validate({"level": "trace"})


def test_base_logging_has_no_environment_prefix() -> None:
    """Applications choose the environment variable namespace in subclasses."""
    assert BaseLogging.model_config.get("env_prefix") == ""


def test_subclass_reads_environment_and_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Application prefixes work with both environment and dotenv settings."""
    monkeypatch.setenv("APP_LOG_LEVEL", "warning")
    assert AppLogging().level == "WARNING"

    monkeypatch.delenv("APP_LOG_LEVEL")
    env_file = tmp_path / ".env"
    env_file.write_text("APP_LOG_LEVEL=error\n", encoding="utf-8")
    assert cast(Any, AppLogging)(_env_file=env_file).level == "ERROR"


def test_config_uses_file_fallbacks_and_independent_root_level(tmp_path: Path) -> None:
    """File defaults are generated without mutating settings-source values."""
    log_file = tmp_path / "app.log"
    config = BaseLogging(level="WARNING", file=log_file, file_level="DEBUG")

    generated = config.config()

    assert config.file_level == "DEBUG"
    assert config.file_format is None
    assert generated["handlers"]["file"]["level"] == "DEBUG"
    assert generated["formatters"]["file"]["format"] == config.format
    assert generated["root"] == {"level": "NOTSET", "handlers": ["console", "file"]}


def test_file_handler_receives_records_below_console_threshold(tmp_path: Path) -> None:
    """The root logger does not prevent more-verbose file logging."""
    log_file = tmp_path / "app.log"
    logger = BaseLogging(
        level="WARNING",
        file=log_file,
        file_level="DEBUG",
    ).get_logger("tests.logging", capture_warnings=None)

    logger.debug("debug-record")

    assert "debug-record" in log_file.read_text(encoding="utf-8")


def test_get_logger_configures_root_and_returns_named_logger() -> None:
    """Logger lookup follows application of the generated root configuration."""
    config = BaseLogging()
    with (
        patch("logging.config.dictConfig") as dict_config,
        patch("logging.captureWarnings") as capture_warnings,
    ):
        logger = config.get_logger("tests.logging")

    dict_config.assert_called_once_with(config.config())
    capture_warnings.assert_called_once_with(True)
    assert logger is logging.getLogger("tests.logging")


def test_get_logger_can_leave_warning_capture_unchanged() -> None:
    """A None warning-capture option makes no captureWarnings call."""
    with (
        patch("logging.config.dictConfig"),
        patch("logging.captureWarnings") as capture_warnings,
    ):
        BaseLogging().get_logger(capture_warnings=None)

    capture_warnings.assert_not_called()
