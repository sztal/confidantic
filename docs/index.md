---
icon: lucide/house
---

# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=main&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/main/LICENSE)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

## Installation

Install `confidantic` using [pip](https://pip.pypa.io/) or [uv](https://docs.astral.sh/uv/):

```
pip install confidantic
```

## Frozen configuration

`BaseConfig` instances are frozen by default, so model fields cannot be
reassigned after validation. Create a modified copy from trusted values with
Pydantic's `model_copy` method:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
	retries: int = 3


config = AppConfig()
updated = config.model_copy(update={"retries": 5})
```

Pydantic's frozen behavior is shallow: mutable values stored in fields are not
recursively frozen. A subclass that intentionally requires field reassignment
can opt out:

```python
from confidantic import BaseConfig, SettingsConfigDict


class MutableAppConfig(BaseConfig):
	model_config = SettingsConfigDict(frozen=False)

	retries: int = 3
```

## Field documentation

`BaseConfig` subclasses automatically replace their NumPy-style `Attributes`
section with the effective model field names and descriptions:

```python
from confidantic import BaseConfig
from pydantic import Field


class AppConfig(BaseConfig):
	"""Application configuration."""

	retries: int = Field(3, description="Number of retry attempts.")
```

Set `docstring_set_attributes_section=False` to preserve a handwritten class
docstring unchanged:

```python
from confidantic import BaseConfig, SettingsConfigDict


class AppConfig(BaseConfig):
	"""Application configuration."""

	model_config = SettingsConfigDict(
		docstring_set_attributes_section=False,
	)
```
