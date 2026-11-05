# confidantic.\_config.\_docstrings

`replace_attributes()` handles class docstrings containing an active `@attrs`
request. It separates source-layout handling from optional parser operations.
Ordinary Pydantic attribute-docstring extraction is a different facility and does
not require this generation path.

## Scan and validate

`_scan_docstring()` creates a dedented scan view with line indices aligned to the
original text. `_SectionSpan` records heading/body boundaries and style. The scanner
recognizes NumPy and Google sections while ignoring markers inside examples,
fenced blocks, and indented literal content.

With no active marker, the original string is returned unchanged. Active requests
must identify exactly one Attributes section and one marker inside it. NumPy uses
the expected underline and standalone marker; Google also accepts `@attrs:`.
An explicit style must match the section. Structural errors become class-qualified
ValueErrors before any optional parser is imported.

## Replace and verify

Only a valid request imports the [\_docstring_backend](_docstring_backend.md).
The backend composes the replacement section. Splicing preserves surrounding text,
heading indentation, trailing surrounding blank lines, and LF/CRLF convention.
The result is scanned again for duplicate sections and leftover markers, then
parsed independently to compare ordered field names and normalized descriptions.

Missing docstring-parser raises an ImportError naming the extra. Parser/internal
errors otherwise retain their intended meaning. Google cannot represent a valid
empty generated section here, while NumPy permits one.

## When changing this module

Preserve the distinction between active directives and literal mentions, structural
validation before imports, and independent post-composition verification. Keep all
scan state local to the call. Do not rewrite the entire docstring through a parser;
that would alter unrelated layout and content.

Evidence: [source](../../../confidantic/_config/_docstrings.py) and
[docstring tests](../../../tests/_config/test_docstrings.py).
See [configuration models](../../concepts/configuration-models.md),
[logging's marked docstring](../../examples/logging.md), and [the index](README.md).
