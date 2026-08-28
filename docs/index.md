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
reassigned after validation. Create a modified copy with `copy`; supplied
updates are validated as normal model input:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
	retries: int = 3


config = AppConfig()
updated = config.copy(retries=5)
```

`copy()` is shallow and `deepcopy()` recursively copies field values. Both
methods accept validated keyword updates. The standard-library `copy.copy()`
and `copy.deepcopy()` functions are also supported.

Use `mutate()` to apply validated updates to the same instance, including a
frozen configuration:

```python
config.mutate(retries=5)
```

Take care when mutating a frozen configuration: changing its fields may
invalidate its hash. Do not continue to use a mutated configuration as a
dictionary key or set member.

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
