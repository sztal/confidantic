# confidantic.\_config.\_docstring_backend

This private optional module owns docstring-parser integration. The scanner imports
it only after validating an active generation request. Callers exchange plain text
and ordered field descriptions; parser-specific objects remain inside the backend.

## Composition and parsing

`_AttributeDocstringBackend` retains one style and a class name for diagnostics.
`compose()` creates attribute entries in field order, with names and descriptions
but no synthesized types or defaults. It supplies an empty heading when the composer
would omit the section, leaving subsequent parsing to decide validity.

`attributes()` parses the complete resulting docstring and returns ordered names
and whitespace-normalized descriptions. NumPy parsing registers discovered custom
headings through `_LiteralNumpySection`, escaping their regex characters. This
keeps unknown sections from being interpreted as more attribute documentation.
Google uses the corresponding standard parser. Newline normalization is confined
to the parser's view.

## When changing this module

Keep parsing independent of composition so malformed output cannot validate itself
merely by reproducing the same layout assumptions. Preserve field order, literal
custom headings, and class-qualified conversion of ParseError to ValueError.
Unexpected dependency failures propagate. There is no global parser cache; backend
objects are scoped to individual generation requests.

Evidence: [source](../../../src/confidantic/_config/_docstring_backend.py) and
[backend tests](../../../tests/_config/test_docstring_backend.py).
See [configuration models](../../concepts/configuration-models.md),
[the marked logging example](../../examples/logging.md), and [the index](README.md).
