# confidantic.logging

`BaseLogging` is the exported settings model for Python logging. Its `config()`
method builds a dictConfig-compatible dictionary; `get_logger()` applies that
dictionary and returns a named or root logger. `LogLevelT` provides the module's
constrained level annotation, normalizing casing and WARN/FATAL aliases.

## Data construction and effects

`config()` constructs a fresh mapping with console formatting and a console handler.
A configured file adds a rotating handler with independent level/format fallbacks.
File paths become absolute relative to the working directory when this method runs;
home markers are not expanded and parent directories are not created.

Building the mapping does not open a file or create a handler. Applying it through
`get_logger()` configures the root logger and replaces its handlers, even when the
returned logger is named. Warning capture is enabled by default; a `None` override
leaves the existing capture policy unchanged. These are process-wide effects.

Pydantic validates declared field constraints. dictConfig owns checks such as its
supported schema version, formatter syntax, and stream references. Those errors
propagate at application time. Root logger and handler levels have distinct roles;
an ancestor logger's level does not refilter an explicitly leveled child's records.

## When changing this module

Keep data preparation separate from handler installation. Preserve level
normalization, file fallback rules, and the choice to leave directory creation
to callers. Subclasses customize settings and sources; applications can inspect
or adapt the dictionary before applying it. Use isolated processes for tests that
alter logging state.

Evidence: [source](../../confidantic/logging.py) and
[logging tests](../../tests/test_logging.py).
See [configuration models](../concepts/configuration-models.md),
[logging examples](../examples/logging.md), and [all modules](README.md).
