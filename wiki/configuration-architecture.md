# Configuration implementation boundaries

`BaseConfig` keeps the public configuration API and Pydantic hook adapters in
[`base.py`](../confidantic/_config/base.py). Implementation collaborators live
in focused modules under `confidantic/_config/`; they do not add another model
inheritance hierarchy or a plugin registry.

## Responsibilities

| Module                  | Responsibility and interface                                                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_options.py`           | `ConfigModelDict` and registration of Confidantic settings keys.                                                                                                                                                                                                     |
| `_settings.py`          | `_SettingsSources.build()` assembles per-MRO sources; `finalize_values()` prepares merged values. `ClassDefaultsSource` supplies class defaults and `_ProvenanceSource` records winning sources. Importable schema callbacks preserve Pydantic validation semantics. |
| `_nested.py`            | `_NestedModelUpdates.scope()` owns one validation call's nested-model baselines. `prepare()` selects baselines and `apply()` performs field updates.                                                                                                                 |
| `_cli.py`               | `_CliSettings.source()` chooses the CLI source and its options; `suppress()` temporarily disables parsing during factory resolution.                                                                                                                                 |
| `_formats.py`           | `dump_yaml()`, `load_yaml()`, and `dump_toml()` load optional format dependencies at the operation boundary. TOML loading uses `tomllib` directly.                                                                                                                   |
| `_info.py`              | `_InfoRenderer.build_table()` and `render()` implement Rich display, loaded only by display methods.                                                                                                                                                                 |
| `_docstrings.py`        | Scans docstring layout, validates insertion requests, and preserves surrounding text without importing a parser.                                                                                                                                                     |
| `_docstring_backend.py` | `_AttributeDocstringBackend` composes and validates generated attributes using the optional parser.                                                                                                                                                                  |
| `factory.py`            | Generates constructor-based models and resolves factory values, sharing the settings schema and CLI suppression interfaces.                                                                                                                                          |

The settings and nested-update collaborators accept model classes, source
collections, or values explicitly. They do not create hidden singletons on
model subclasses. `BaseConfig` retains the overridable source-building hooks,
so subclass customization and upstream Pydantic Settings options continue to
flow through the same entry points.

## Validation state and serialization

Nested-update baselines belong to a single validation scope. A context variable
connects that scope to field validators, and its token is reset on success or
failure. Nested validation temporarily replaces the active scope and restores
the outer scope afterward. CLI suppression has a separate context variable
because factory resolution can surround multiple validation calls.

The state remains in importable modules. It is not attached to dynamic model
classes or captured in generated schema callbacks, allowing current-version
models and factory defaults to transfer through cloudpickle and worker
processes without copying ambient execution state.

Public imports from `confidantic` remain stable. Internal module paths and
previously serialized Python payloads are not compatibility interfaces for this
refactor; there are no aliases preserving the previous internal layout. Rebuild
such payloads with the current version. Portable configuration documents retain
their public validation and serialization APIs.

The known per-call option limitation in nested-model reconstruction remains
documented in [`BUGS.md`](../BUGS.md); reorganizing the implementation does not
change the validation policy.

## Optional integrations

Core imports, source-level attribute-docstring extraction, settings, CLI parsing,
and factory resolution do not import Rich, docstring-parser, PyYAML, or tomli-w.
Their installation extras are `rich`, `docstrings`, `yaml`, and `toml`; `all`
enables all four.

Missing optional packages produce an `ImportError` naming the relevant extra at
the feature boundary. Errors inside an installed package propagate unchanged.
An active `@attrs` request is validated structurally before the parser loads:
malformed requests raise `ValueError`, and valid requests require `docstrings`.
Ignored markers and disabled generation never load the parser.

Rich return annotations remain available for static checking. Runtime
`typing.get_type_hints()` on display methods requires a namespace containing
`Table`; `inspect.signature()` and ordinary model creation do not require Rich.

The `optional-deps` Nox check builds one wheel and verifies six fresh
installations using the default interpreter: core, each extra individually,
and all extras together. Smoke checks run outside the repository with isolated
import paths and verify that Confidantic loads from the installed wheel.
