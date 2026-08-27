"""Configuration and CLIs for Python projects based on Pydantic Settings."""

from __future__ import annotations

__all__ = (
    "BaseConfig",
    "BaseContext",
    "ClassDefaultsSource",
    "SettingsConfigDict",
    "__version__",
)

import importlib.metadata

from confidantic.config import (
    BaseConfig,
    BaseContext,
    ClassDefaultsSource,
    SettingsConfigDict,
)

__version__ = importlib.metadata.version("confidantic")
