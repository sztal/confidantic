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

## Model strings

Pass `context={"model_string": True}` to `model_dump()` or
`model_dump_json()` to add an import string for each serialized `BaseConfig`:

```python
config.model_dump(context={"model_string": True})
# {"__model__": "package.module:AppConfig", "retries": 3}
```

The special key is configured with `model_import_string` in
`SettingsConfigDict` and defaults to `"__model__"`. Set it to `None` to exclude
a configuration class from this output. Nested `BaseConfig` instances receive
their own marker; ordinary Pydantic models do not.

Marked configuration data can be deserialized polymorphically with
`model_validate()` or `model_validate_json()`:

```python
config = BaseConfig.model_validate(data)
```

The imported model must be a `BaseConfig` subclass of the requested type;
otherwise validation raises an error. For validation through a base type, every
participating configuration must use the same `model_import_string` key, which
defaults to `"__model__"`. This feature is intended for trusted serialized data:
the marker controls an import. Direct model construction is not polymorphic.

## YAML and TOML

Install an optional writer to serialize configurations as YAML or TOML:

```console
pip install "confidantic[yaml]"
pip install "confidantic[toml]"
```

Both methods accept the same model-dump filtering, context, and serialization
options as `model_dump_json()` and return a string:

```python
yaml_text = config.model_dump_yaml(context={"model_string": True})
toml_text = config.model_dump_toml(exclude_none=True)
```

YAML uses block formatting and preserves model field order, including a leading
model string. TOML has no null representation, so use `exclude_none=True` when
the configuration can contain `None` values.
