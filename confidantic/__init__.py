"""Configuration and CLIs for Python projects based on Pydantic Settings."""

__all__ = (
    "BaseConfig",
    "BaseContext",
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

__version__ = importlib.metadata.version("confidantic")
