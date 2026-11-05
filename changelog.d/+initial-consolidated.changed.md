Configuration fields are frozen and defaults are validated by default. Set
`frozen=False` explicitly for mutable configurations. Environment parsing requires
an explicit `env_prefix`; use an empty string for unprefixed process variables.
An unset prefix still permits dotenv configuration. Boolean CLI fields require
explicit values unless `cli_implicit_flags=True`. Environment-variable names are
hidden from help unless `cli_show_env_vars=True` and a string prefix is set.

Use generic `Factory[T]` fields, `__name__` and `__recursive__` generation options,
and explicit `model_resolve()` calls. Earlier development snapshots used
`FactoryConfig`, `FactoryField`, `as_factory`, `model_factory()`, callable factories,
and `materialize()`. Apply configuration updates before resolution; the old
resolution-time updates and recursion switch are no longer supported.

Rich display and marked attribute-docstring generation require the `rich` and
`docstrings` extras. `confidantic[all]` includes these plus YAML and TOML support.
Core imports do not load optional packages. Missing extras produce informative
errors, while structural marker errors and failures inside installed dependencies
retain their original meaning. Attribute-docstring source inspection is disabled
by default in Jupyter-like runtimes.

Configuration internals are organized into focused modules. Recreate Python
payloads serialized by earlier development snapshots; old internal import paths
are not preserved. Current-version fresh-process serialization remains supported.
Runtime type-hint evaluation of Rich display methods needs a namespace containing
`Table`.

Release notes are consolidated only when merging into `master`. Releases derive
versions from annotated Git tags and are prepared locally in isolated checkouts.
Tag pushes validate only; explicit publishing sends candidates to TestPyPI and
final releases to PyPI after checking the exact distributions. Candidate releases
retain pending notes until the final release.
