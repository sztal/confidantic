# Annotation reference

Import these names from `confidantic.annotations`. They work on typed fields and,
where appropriate, with Pydantic's `TypeAdapter`. Start with the
[input parsing guide](../guide/input-parsing.md) for examples.

## Text and collections

| Annotation                                                       | Input convenience                                                                    |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| \[`Delimited(separator)[T]`\][confidantic.annotations.Delimited] | Normal validation, then JSON, then delimiter splitting for strings                   |
| `CommaDelimited[T]`                                              | Comma-separated values                                                               |
| `SemiColonDelimited[T]`                                          | Semicolon-separated values                                                           |
| `TabDelimited[T]`                                                | Tab-separated values                                                                 |
| `WhitespaceDelimited[T]`                                         | Values separated by runs of whitespace                                               |
| `Map[T]`                                                         | Mappings, JSON objects, or key/value text                                            |
| `NoDecode`                                                       | Pydantic Settings annotation, re-exported here, that suppresses source JSON decoding |

Parameterize with the complete desired type, such as `CommaDelimited[list[int]]`
or `Map[dict[str, int]]`. Item validation remains active. `Map` accepts pairs
separated by commas or whitespace before a new key, splits values at the first
equals sign, and keeps the last repeated key. Parsing has no quoting or escaping;
use JSON for embedded separators. Explicit delimiters preserve empty items.

These parsing annotations already carry `NoDecode`. CLI sources may still normalize
list or mapping syntax before field validation. If fallback parsing fails, the
original validation error is retained.

## Paths

`AbsolutePath` validates a
[pathlib.Path][] and resolves it against the working directory. It follows symlinks
but does not expand `~`. A parameter such as `AbsolutePath[FilePath]` retains the
constraint's check before resolution. Existence is not otherwise required.

For shared roots, anchors, and callable path joining, see
[BasePaths and ExtensiblePath](../recipes/paths.md).

## Imports and executable directives

| Annotation  | Operation                                                              |
| ----------- | ---------------------------------------------------------------------- |
| `Import[T]` | Import an object and validate it as `T`                                |
| `Call[T]`   | Evaluate one call; leave nested arguments unchanged                    |
| `Make[T]`   | Recursively evaluate supported nested directives, then validate as `T` |

These annotations accept trusted input only: imports and calls can execute code.
See [object directives](../advanced/object-directives-and-portability.md) for syntax,
portability, and serialization. Ordinary nested strings remain data during `Make`
traversal; top-level strings can request construction.

## Annotation inspection

[get_proper_args][confidantic.annotations.get_proper_args] yields type-valued leaves
from annotation arguments, including type-valued `Annotated` metadata. It does not
normalize an annotation into the types accepted at runtime. This helper is mainly
useful when building integrations; it is not required to use the annotations above.
