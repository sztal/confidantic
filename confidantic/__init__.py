"""Configuration and CLIs for Python projects based on Pydantic Settings."""

__all__ = (
    "BaseConfig",
    "BaseContext",
    "BaseLogging",
    "BasePaths",
    "ClassDefaultsSource",
    "DynamicPath",
    "FactoryConfig",
    "SettingsConfigDict",
    "__version__",
)

import importlib.metadata

from confidantic.config import (
    BaseConfig,
    BaseContext,
    BasePaths,
    ClassDefaultsSource,
    DynamicPath,
    FactoryConfig,
    SettingsConfigDict,
)
from confidantic.logging import BaseLogging

__version__ = importlib.metadata.version("confidantic")
