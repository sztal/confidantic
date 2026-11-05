Removed the `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS` environment override; configure
`use_attribute_docstrings` per model. Removed the obsolete `model_import_string`
option and legacy `__model__` marker; use `Make[...]` with `@call` mappings for
directive-based construction.
