Make Rich display and `@attrs` docstring generation optional through
`confidantic[rich]` and `confidantic[docstrings]`; `confidantic[all]` includes both
along with YAML and TOML support. Core imports, settings, factories, and Pydantic
attribute-docstring extraction no longer import these packages. Feature calls
raise an informative `ImportError` when their dependency is missing, while
invalid marker requests retain structural validation before parser loading.
Import failures inside an optional package propagate without being mislabeled
as a missing extra.

Reorganize configuration internals into focused modules while retaining public
package exports and method signatures. Previous internal import paths and
previously serialized Python payloads are not retained; recreate those payloads
with the current version. Fresh-process serialization within the current
version remains supported. Runtime `typing.get_type_hints()` for Rich display
methods now requires an explicit namespace supplying `Table`.
