---
icon: lucide/house
---

# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=main&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![Package build](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/release.yaml?branch=main&logo=github&label=package%20build)](https://github.com/sztal/confidantic/actions/workflows/release.yaml)
[![Coverage](https://sztal.github.io/confidantic/coverage.svg)](coverage/)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/main/LICENSE)

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
from confidantic import BaseConfig, ConfigModelDict


class MutableAppConfig(BaseConfig):
	model_config = ConfigModelDict(frozen=False)

	retries: int = 3
```

## Field documentation

Confidantic reads attribute docstrings into field descriptions by default.
Extraction is disabled automatically in Jupyter-like runtimes, including VS Code
Interactive, where source inspection can fail.

Set `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS` before importing Confidantic to
explicitly enable or disable extraction for the package:

```console
CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS=false python app.py
```

Values use Pydantic's boolean parsing: for example, `true`, `yes`, `on`, and `1`
enable extraction; `false`, `no`, `off`, and `0` disable it, regardless of case.
An empty or invalid value raises `ValueError` during import. An explicit value
overrides notebook detection. If unset, extraction remains enabled outside
Jupyter-like runtimes.

The variable is read once when the package is imported, directly from the
process environment. Settings prefixes and dotenv files do not affect it;
changing the environment afterward does not update the default. Set it before
starting worker processes as well when their source inspection is unavailable.
An explicit `model_config = ConfigModelDict(use_attribute_docstrings=...)` on a
configuration class takes precedence over the package default.

Disabling extraction does not remove explicit `Field(description=...)`
descriptions or disable the `@attrs` replacement below.

Add an `@attrs` marker to a `BaseConfig` subclass's NumPy or Google `Attributes`
section to replace the entire section with effective model field names and descriptions.
The format is detected automatically, and text outside the section is preserved:

```python
from confidantic import BaseConfig
from pydantic import Field


class AppConfig(BaseConfig):
	"""Application configuration.

	Attributes
	----------
	@attrs
	"""

	retries: int = Field(3, description="Number of retry attempts.")
```

Google sections accept either `@attrs` or `@attrs:`:

```python
from confidantic import BaseConfig, ConfigModelDict
from pydantic import Field


class AppConfig(BaseConfig):
    """Application configuration.

    Attributes:
        @attrs
    """

    model_config = ConfigModelDict(docstring_style="google")
    retries: int = Field(3, description="Number of retry attempts.")
```

`docstring_style` accepts `"numpy"`, `"google"`, or `None` (the default, for
automatic detection). The setting is inherited; set it to `None` on a subclass
to restore detection. An explicit style specifies the expected input format
and does not convert docstrings.

Generation validates the completed docstring using the selected parser and
requires exactly one Attributes section with the generated fields. Invalid
marked sections, conflicting styles, duplicate sections, and invalid generated
output raise `ValueError` during class creation. An empty marked Google section
also raises because the parser requires an attribute entry; an empty NumPy
section is accepted. Unmarked docstrings and marker mentions in prose, examples,
or nested literal content are unchanged.

Set `docstring_set_attributes_section=False` to retain an `@attrs` marker
without replacing it:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
	"""Application configuration.

	Attributes
	----------
	@attrs
	"""

	model_config = ConfigModelDict(
		docstring_set_attributes_section=False,
	)
```

## Make directives

Pass `context={"make": True}` to `model_dump()` or `model_dump_json()` to add
a `Make` directive for each serialized `BaseConfig`:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
    retries: int = 3


config = AppConfig()
data = config.model_dump(context={"make": True})
# {"@call": "package.module:AppConfig", "retries": 3}
```

Nested `BaseConfig` instances receive their own directive; ordinary Pydantic
models do not. A `Factory` writes its target class's identifier, so loading
its directive constructs the target object. Identifiers must resolve to
importable objects; local and unregistered generated classes are not portable.
Use `serialize_as_any=True` when fields annotated with base classes must retain
subclass-only data.

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

Both methods accept model-dump filtering, context, and serialization options
and return a string. Ordinary documents can be loaded directly:

```python
yaml_text = config.model_dump_yaml()
toml_text = config.model_dump_toml(exclude_none=True)

loaded_yaml = AppConfig.model_validate_yaml(yaml_text)
loaded_toml = AppConfig.model_validate_toml(toml_text)
```

YAML uses block formatting and preserves model field order, including a leading
Make directive. TOML has no null representation, so use `exclude_none=True` when
model fields can contain `None`. This does not remove `None` entries inside
lists or mappings; those require preprocessing. The YAML loader requires the
YAML extra; TOML loading uses Python's standard library. Both loaders parse into
Python values and forward their validation options to `model_validate()`.
Configured settings sources can still participate in construction.

The loaders do not evaluate a root `@call` directive. For output produced with
`context={"make": True}`, parse the document and validate it through `Make`:

```python
import yaml
from pydantic import TypeAdapter
from confidantic.annotations import Make


yaml_text = config.model_dump_yaml(context={"make": True})
loaded_yaml = TypeAdapter(Make[AppConfig]).validate_python(yaml.safe_load(yaml_text))
```
