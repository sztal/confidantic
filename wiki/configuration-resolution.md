# Configuration resolution

`BaseConfig` extends Pydantic Settings with inheritance-aware configuration
resolution. A concrete class is resolved before its parent classes in Python's
C3 MRO, so a child can provide defaults or sources without losing the normal
Pydantic Settings behavior.

## Source precedence

When CLI parsing is enabled, sources are checked in descending priority:

1. CLI arguments.
1. Explicit initialization arguments.
1. Process environment variables.
1. Dotenv values.
1. Secret files.
1. Defaults declared by the current class.

The first value found for a field wins. Nested mappings and models are merged,
so lower-priority sources can supply keys that remain absent. Values still
missing after the current class's defaults advance to the next parent in the
MRO. A default on a derived class therefore takes priority over a source that
applies only to a parent.

A simple configuration can declare its input namespace and dotenv file through
`ConfigModelDict`:

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
```

See [`examples/basic.py`](../examples/basic.py) for an executable walkthrough,
[`examples/cli.py`](../examples/cli.py) for CLI input, and
[`examples/env_files.py`](../examples/env_files.py) for dotenv discovery.

## Custom sources

JSON, TOML, YAML, and `pyproject.toml` sources are opt-in. A subclass registers
them through `settings_customise_sources`, which returns source callables in
descending priority. This makes the placement of each structured file explicit
rather than assigning it an implicit position.

Pydantic Settings still supplies the source machinery for an individual level;
`BaseConfig` preserves its deep-merge behavior across the flattened MRO source
sequence. File-backed source paths follow Pydantic Settings configuration:
dotenv and secrets have built-in initializer overrides, while structured file
paths are supplied by the subclass when it constructs the source.

## Field provenance

Each resolved instance exposes `model_field_sources`, a read-only mapping from
canonical field names to the source class and configuration class that
established each field. For example, a child-level environment value is
attributed to `(EnvSettingsSource, ChildConfig)`, while an inherited default is
attributed to `(ClassDefaultsSource, ParentConfig)`.

Provenance is field-level: nested values may come from several sources, but the
mapping reports the source that first established the top-level field. Computed
values and values created only during validation have no source coordinate.
Bare custom callables can still resolve settings, but cannot provide provenance
because they do not expose the required source state.

The implementation lives in [`confidantic/_config/base.py`](../confidantic/_config/base.py).
The package-level overview is in [`baseconfig-resolution-order.md`](baseconfig-resolution-order.md).
