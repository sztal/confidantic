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

Add an `@attrs` marker to a `BaseConfig` subclass's NumPy-style `Attributes`
section to replace it with effective model field names and descriptions:

```python
from confidantic import BaseConfig
from pydantic import Field


class AppConfig(BaseConfig):
	"""Application configuration."""

	Attributes
	----------
	@attrs

	retries: int = Field(3, description="Number of retry attempts.")
```

Set `docstring_set_attributes_section=False` to retain an `@attrs` marker
without replacing it:

```python
from confidantic import BaseConfig, SettingsConfigDict


class AppConfig(BaseConfig):
	"""Application configuration."""

	Attributes
	----------
	@attrs

	model_config = SettingsConfigDict(
		docstring_set_attributes_section=False,
	)
```

## Make directives

Pass `context={"make": True}` to `model_dump()` or `model_dump_json()` to add
a `Make` directive for each serialized `BaseConfig`:

```python
config.model_dump(context={"make": True})
# {"@call": "package.module:AppConfig", "retries": 3}
```

Nested `BaseConfig` instances receive their own directive; ordinary Pydantic
models do not.

Deserialize the result with the `Make` annotation:

```python
from confidantic.annotations import Make
from pydantic import BaseModel


class Container(BaseModel):
	config: Make[AppConfig]


config = Container.model_validate({"config": data}).config
```

This feature is intended for trusted serialized data: the directive controls an
import and invokes the selected class constructor.

## YAML and TOML

Install an optional writer to serialize configurations as YAML or TOML:

```console
pip install "confidantic[yaml]"
pip install "confidantic[toml]"
```

Both methods accept the same model-dump filtering, context, and serialization
options as `model_dump_json()` and return a string:

```python
yaml_text = config.model_dump_yaml(context={"make": True})
toml_text = config.model_dump_toml(exclude_none=True)

loaded_yaml = AppConfig.model_validate_yaml(yaml_text)
loaded_toml = AppConfig.model_validate_toml(toml_text)
```

YAML uses block formatting and preserves model field order, including a leading
Make directive. TOML has no null representation, so use `exclude_none=True` when
the configuration can contain `None` values. The YAML loader requires the YAML
extra; TOML loading uses Python's standard library. Both loaders forward their
validation options to `model_validate()`.
