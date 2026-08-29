"""Configuration and CLIs for Python projects based on Pydantic Settings."""

__all__ = (
    "BaseConfig",
    "BaseContext",
    "ClassDefaultsSource",
    "FactoryConfig",
    "SettingsConfigDict",
    "__version__",
)

import importlib.metadata

from confidantic._config import (
    BaseConfig,
    BaseContext,
    ClassDefaultsSource,
    FactoryConfig,
    SettingsConfigDict,
)

__version__ = importlib.metadata.version("confidantic")
