"""Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.."""

from __future__ import annotations

__all__ = ("__version__",)

import importlib.metadata

__version__ = importlib.metadata.version("confidantic")
