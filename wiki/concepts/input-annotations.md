# Input annotations

Smart annotations adapt common configuration input while retaining Pydantic's
validation of the requested type. Use them on BaseConfig or ordinary BaseModel
fields; most do not depend on settings construction.

## Paths and text input

`AbsolutePath` validates a pathlib path and resolves it against the current working
directory. A parameter such as `AbsolutePath[FilePath]` adds validation before
resolution. It does not expand home markers; BasePaths provides a separate root
and anchor policy.

`Delimited(separator)[T]` first attempts ordinary validation, then JSON decoding,
then splitting for string input. The named aliases choose common separators.
Whitespace splitting collapses runs; explicit separators preserve empty items.
`Map[T]` similarly accepts ordinary mappings, JSON, or key/value text. Pair values
split at the first equals sign and repeated keys keep the last value. Neither
syntax provides quoting/escaping: use JSON for embedded separators.

These annotations carry NoDecode so settings sources leave their strings available
to the annotation validator. Pydantic Settings CLI parsing can still normalize list
or mapping syntax first; environment and command-line representations need not be identical.

## Importing and executing

| Annotation  | Meaning                                                                    |
| ----------- | -------------------------------------------------------------------------- |
| `Import[T]` | Resolve an object identifier and validate the imported object as T         |
| `Call[T]`   | Evaluate one call and validate its result as T                             |
| `Make[T]`   | Evaluate nested supported directives and validate the completed value as T |

Call and Make treat top-level strings as import-and-call requests. An `@call` mapping
can supply `@args` and keyword entries. Call leaves nested arguments untouched;
Make visits mapping values, lists, and tuples, preserving ordinary nested strings
and callables as data. Neither automatically stores the original directive for dumping.
Use executable directives with trusted input because they import and invoke code.

See [smart annotation examples](../examples/smart-annotations.md),
[annotation internals](../api/annotations.md), and [directive evaluation](../api/utils.md).
Return to [all concepts](README.md).
