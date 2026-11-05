# Optional integrations

Core configuration, CLI parsing, factories, and attribute-docstring extraction work
without optional integrations. Extras are loaded where their operations are used,
so importing the core package does not require presentation or document writers.

| Extra        | Feature boundary                           | Implementation                                                                                                    |
| ------------ | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `rich`       | Any `model_info()` or `info()` output mode | [base](../api/_config/base.md) lazily imports [\_info](../api/_config/_info.md)                                   |
| `docstrings` | Valid active class `@attrs` generation     | [\_docstrings](../api/_config/_docstrings.md) imports [\_docstring_backend](../api/_config/_docstring_backend.md) |
| `yaml`       | YAML loading and dumping                   | [\_formats](../api/_config/_formats.md) imports PyYAML                                                            |
| `toml`       | TOML dumping                               | [\_formats](../api/_config/_formats.md) imports tomli-w                                                           |
| `all`        | All of the above                           | Dependency aggregation                                                                                            |

TOML loading uses the standard library. Ordinary field-description extraction comes
from Pydantic and is distinct from generation of a class Attributes section.

## Error and side-effect ordering

A missing requested package raises an ImportError naming the relevant extra.
Failures inside an installed package must propagate rather than being mistaken for
a missing integration. Format dependencies load before user model serializers run.

Docstring requests are structurally checked before importing the parser. Malformed
active markers raise ValueError; unmarked docstrings, literal marker mentions, and
explicitly disabled generation need no parser. Valid generation occurs at class
creation, so that feature can require its extra earlier than a runtime method call.

Rich return annotations remain available for static checking without a runtime import
at model creation. Runtime `typing.get_type_hints()` on display methods needs a
namespace containing Table; ordinary signature inspection does not import Rich.

## Verification

[Optional-dependency tests](../../tests/integration/test_optional_dependencies.py)
exercise feature boundaries. The repository's optional-deps check builds and tests
core, individual extras, and all extras in isolated installations outside the checkout,
preventing development dependencies from masking missing runtime dependencies.

When documenting an example, include dependencies of its display and class-definition
steps as well as its main operation. The logging guide uses a marked docstring and
therefore needs `docstrings`; template guides call `info()` and need `rich`.
See [logging](../examples/logging.md), [serialization](../examples/serialization.md),
and [configuration concepts](../concepts/configuration-models.md).
Return to [architecture](README.md).
