# Confidantic package design and usage

Confidantic builds configuration and CLI workflows on top of Pydantic and
Pydantic Settings. Its central abstraction is `BaseConfig`: a validated,
frozen settings model that combines constructor arguments, CLI arguments,
environment variables, dotenv files, secret files, and class defaults.

## Package map

The implementation is layered around `BaseConfig`; the specialized APIs reuse
its validation and source-resolution behavior:

- [`BaseConfig`][baseconfig] and `ClassDefaultsSource` provide settings
  resolution, inherited defaults, frozen models, copying, mutation, field
  provenance, and serialization helpers.
- [`Factory`][factory] creates configuration models from class constructors.
- [`confidantic.annotations`][annotations] provides reusable annotations for
  paths, delimited values, mappings, imports, calls, and trusted make
  directives.
- [`BaseContext`][context] provides context-local configuration and scoped
  overrides.
- [`Configurable`][configurable], [`paths`][paths], [`logging`][logging], and
  [`types`][types] provide integrations for configurable objects, path-aware
  fields, logging settings, and shared model types.

Read the focused pages for details:

- [Configuration resolution](configuration-resolution.md)
- [Factories and annotations](factories-and-annotations.md)
- [Contexts and serialization](contexts-and-serialization.md)

## Quick start

Define fields as you would with a Pydantic model. Configure the input namespace
and optional CLI parsing with `ConfigModelDict`:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(
        env_prefix="APP_",
        env_file=".env",
        cli_parse_args=True,
    )

    name: str = "demo"
    retries: int = 3


config = AppConfig()
updated = config.copy(retries=5)
```

For a runnable walkthrough of source precedence, see
[`examples/basic.py`](../examples/basic.py). The complete runnable guide set is
in [`examples/`](../examples/), including CLI, dotenv, nested, factory,
context, logging, and serialization examples. They are smoke-tested by
[`tests/test_examples.py`](../tests/test_examples.py).

## Public references

The generated [API reference](../docs/reference/api.md) is the public symbol
index. Source-level implementation details live in [`confidantic/`](../confidantic/),
and behavioral details belong in the focused tests under [`tests/`](../tests/).

[annotations]: ../confidantic/annotations.py
[baseconfig]: ../confidantic/_config/base.py
[configurable]: ../confidantic/configurable.py
[context]: ../confidantic/context.py
[factory]: ../confidantic/_config/factory.py
[logging]: ../confidantic/logging.py
[paths]: ../confidantic/paths.py
[types]: ../confidantic/types.py
