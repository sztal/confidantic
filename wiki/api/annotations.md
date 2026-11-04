# confidantic.annotations

This module defines public annotation aliases and the `Delimited` annotation
factory. Pydantic owns validation of the resulting type; Confidantic wraps that
validation to adapt input. `NoDecode` is a re-export from Pydantic Settings.

## Validation paths

| Annotation                | Processing                                                          |
| ------------------------- | ------------------------------------------------------------------- |
| `AbsolutePath[P]`         | Validate the path type, then call `resolve()`                       |
| `Delimited(separator)[T]` | Try ordinary validation, JSON input, then split text                |
| `Map[T]`                  | Try ordinary validation, JSON input, then key/value pairs           |
| `Import[T]`               | Resolve an import through Pydantic and serialize its identifier     |
| `Call[T]`                 | Evaluate one top-level call, then validate its result               |
| `Make[T]`                 | Recursively evaluate supported directives, then validate the result |

Delimited aliases select comma, semicolon, tab, or whitespace splitting. Delimited
and Map carry `NoDecode` so environment-source JSON decoding does not preempt their
fallbacks. CLI parsing can still normalize input before these validators run.
Failed parsing fallbacks preserve the original validation exception, chaining the
last error. Pair syntax has no quoting or escaping; repeated Map keys keep the last
value. Use JSON when values contain separators.

`AbsolutePath` follows symlinks and resolves relative to the current directory;
it does not expand `~`. Constraints such as `FilePath` run before resolution.
`Import` serialization records an identifier without proving that it can be imported.

## Ownership and preservation rules

Aliases contain validator metadata, not model-specific mutable state. Each
`Delimited` call closes over its separator. Directive execution is delegated to
[`utils`](utils.md); Call does not recursively preprocess arguments, whereas Make
does. Their results still undergo the requested Pydantic validation.

`get_proper_args` recursively yields type-valued annotation leaves, including
type-valued Annotated metadata, without deduplication. Do not reinterpret it as
the set of accepted runtime types. When editing annotations, preserve validator
ordering, ordinary-input behavior, and the distinctions between top-level and
nested directives. Errors from imports and called code must remain visible.

Evidence: [source](../../confidantic/annotations.py) and
[annotation tests](../../tests/test_annotations.py).
Read [input annotations](../concepts/input-annotations.md), run
[smart annotations](../examples/smart-annotations.md), or return to
[the module index](README.md).
