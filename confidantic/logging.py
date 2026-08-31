"""Configurable logging base class.

Provides :class:`BaseLogging`, a pydantic-settings model that builds a
``logging.config.dictConfig``-compatible dictionary with a console handler
and an optional rotating-file handler.
"""

import logging.config
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BeforeValidator, PositiveInt

from ._config import BaseConfig, ConfigModelDict

__all__ = ("BaseLogging",)


def _canonicalize_log_level(value: str) -> str:
    """Convert standard logging aliases to their canonical names."""
    return {"WARN": "WARNING", "FATAL": "CRITICAL"}.get(value, value)


#: Constrained type for standard Python log-level names.
#: Accepts any casing and the ``WARN``/``FATAL`` aliases.
LogLevelT = Annotated[
    Literal[
        "NOTSET",
        "DEBUG",
        "INFO",
        "WARNING",
        "WARN",
        "ERROR",
        "CRITICAL",
        "FATAL",
    ],
    BeforeValidator(str.upper),
    AfterValidator(_canonicalize_log_level),
]


class BaseLogging(BaseConfig):
    """Base configuration for application logging.

    Concrete subclasses choose their settings sources, including any environment
    variable prefix, dotenv file, and CLI parsing policy.
    """

    model_config = ConfigModelDict(dotenv_filtering="only_existing")

    stream: str = "ext://sys.stderr"
    """The stream to which logging output will be sent."""
    level: LogLevelT = "INFO"
    """The logging level for the console handler."""
    root_level: LogLevelT = "NOTSET"
    """The logging level at which the root logger admits records."""
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    """The log message format for the console handler."""
    file: Path | None = None
    """The file to which logging output will be written.
    If ``None``, file logging is disabled."""
    file_level: LogLevelT | None = None
    """The logging level for the file handler.
    If ``None``, defaults to the value of ``level``."""
    file_format: str | None = None
    """The log message format for the file handler.
    If ``None``, defaults to the value of ``format``."""
    file_max_bytes: PositiveInt = 5 * 1024 * 1024
    """The maximum size in bytes of the log file before it is rotated."""
    file_backup_count: PositiveInt = 3
    """The number of backup log files to keep when rotating."""
    version: PositiveInt = 1
    """The version of the logging configuration schema."""
    disable_existing_loggers: bool = False
    """Whether to disable existing loggers when configuring logging."""

    def config(self) -> dict[str, Any]:
        """Return a :func:`logging.config.dictConfig`-compatible dictionary.

        Builds a configuration dict with:

        - A ``"console"`` :class:`~logging.StreamHandler` writing to
          :attr:`stream` at :attr:`level`.
        - An optional ``"file"`` :class:`~logging.handlers.RotatingFileHandler`
          (only present when :attr:`file` is set).

        Returns
        -------
        dict[str, Any]
            Dictionary suitable for passing directly to
            :func:`logging.config.dictConfig`.
        """
        handlers: dict[str, dict[str, Any]] = {
            "console": {
                "class": "logging.StreamHandler",
                "level": self.level,
                "formatter": "default",
                "stream": self.stream,
            }
        }

        if self.file:
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": self.file_level or self.level,
                "formatter": "file",
                "filename": str(self.file.absolute()),
                "maxBytes": self.file_max_bytes,
                "backupCount": self.file_backup_count,
            }

        root_handlers: list[str] = ["console"]
        if self.file:
            root_handlers.append("file")

        return {
            "version": self.version,
            "disable_existing_loggers": self.disable_existing_loggers,
            "formatters": {
                "default": {
                    "format": self.format,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                **(
                    {
                        "file": {
                            "format": self.file_format or self.format,
                            "datefmt": "%Y-%m-%d %H:%M:%S",
                        }
                    }
                    if self.file
                    else {}
                ),
            },
            "handlers": handlers,
            "root": {
                "level": self.root_level,
                "handlers": root_handlers,
            },
        }

    def get_logger(
        self,
        logger_name: str | None = None,
        *,
        capture_warnings: bool | None = True,
    ) -> logging.Logger:
        """Apply this logging configuration and return a logger.

        The generated configuration always applies to the root logger.

        Parameters
        ----------
        logger_name : str | None, default None
            Name of the logger to return. If None, return the root logger.
        capture_warnings : bool | None, default True
            Forwarded to :func:`logging.captureWarnings`. When ``True``, Python
            :mod:`warnings` are redirected into the logging system. When
            ``None``, capture behaviour is left unchanged.

        Returns
        -------
        logging.Logger
            The root logger when ``logger_name`` is ``None``, otherwise the named
            logger returned by :func:`logging.getLogger`.
        """
        logging.config.dictConfig(self.config())
        if capture_warnings is not None:
            logging.captureWarnings(capture_warnings)
        return logging.getLogger(logger_name)
