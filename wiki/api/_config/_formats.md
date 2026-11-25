# confidantic.\_config.\_formats

Private helpers convert JSON-mode model dumps to YAML or TOML and parse YAML.
The public methods live on BaseConfig. TOML loading uses `tomllib` in the base
module, so this module needs an optional dependency only for TOML writing.

## Codec boundaries

`dump_yaml` loads PyYAML before invoking model serialization, then uses safe_dump
with Unicode enabled, block formatting, and key sorting disabled. Field order and
a leading Make directive are therefore retained. `load_yaml` uses safe_load and
returns its parsed Python value, which may be a mapping, sequence, scalar, or None.
Validation is the caller's responsibility.

`dump_toml` loads tomli-w before serialization and forwards a JSON-mode dump to the
writer. It does not silently remove unsupported values. `exclude_none=True` can
remove model fields but does not recursively remove null entries in containers.
Writer errors remain visible.

Each loader catches ModuleNotFoundError only when the missing module is the requested
optional package. It raises an installation-oriented ImportError in that case;
errors inside an installed package propagate. The small protocols describe the
operations needed from optional modules without requiring their imports for typing.

## When changing this module

Preserve dependency-before-serialization ordering so a missing codec cannot run user
serializers first. Keep model dump filtering/context delegated to Pydantic, avoid
evaluating directives while parsing, and retain parser/writer errors. There is no
model cache or persistent codec state here.

Evidence: [source](../../../src/confidantic/_config/_formats.py),
[format tests](../../../tests/_config/test_formats.py), and
[optional-dependency tests](../../../tests/integration/test_optional_dependencies.py).
See [serialization concepts](../../concepts/serialization.md),
[the guide](../../examples/serialization.md), and [the index](README.md).
