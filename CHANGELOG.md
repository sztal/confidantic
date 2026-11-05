# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/).

<!-- towncrier release notes start -->

## [0.1.0](https://github.com/sztal/confidantic/tree/v0.1.0) - 2026-11-05

### Removed

- Removed the `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS` environment override; configure
  `use_attribute_docstrings` per model. Removed the obsolete `model_import_string`
  option and legacy `__model__` marker; use `Make[...]` with `@call` mappings for
  directive-based construction.

### Added

- Initial release of Confidantic, with Pydantic Settings configuration and command-line interfaces.

  Generate typed configuration models with `Factory[T].model_from()` and defaults with
  `Factory[T].instance_from()`. `__recursive__` converts selected concrete defaults
  into nested factory fields and enables nested CLI options. Constructor arguments
  can seed generated defaults. Resolve targets explicitly with `model_resolve()`
  on factories and containing `BaseConfig` models; resolution recursively handles
  nested factories and disables CLI parsing during target construction.

  Use `BaseContext` for persistent and temporary context-local configuration,
  `BaseLogging` for console and rotating-file logging, and `BasePaths` with
  `ExtensiblePath` for canonical paths relative to a root. Calling a `BasePaths`
  instance joins paths to that root.

  Inspect settings provenance with `model_field_sources`, copy configurations with
  validated `copy()` and `deepcopy()`, and explicitly update instances with
  `mutate()`. Render model and instance information through `model_info()` and
  `info()` with the Rich extra.

  Read and write YAML and TOML using the corresponding model validation and dump
  methods. Enable dotenv discovery through `env_file_discovery` and override
  `BaseConfig.find_dotenv()` when needed. Suppress CLI help per configuration with
  `cli_help`.

  Generate NumPy or Google attribute documentation using explicit `@attrs` markers,
  with automatic format detection and inherited `docstring_style`. Invalid marked
  sections raise errors and surrounding handwritten text is preserved. Set
  `docstring_set_attributes_section=False` to disable generation.

### Changed

- Configuration fields are frozen and defaults are validated by default. Set
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

### Fixed

- Partial settings updates retain concrete nested model types and existing values
  from defaults and default factories. Per-call strictness, extra policy, and
  validation context reach settings assembly before user validators; custom
  constructors, strict JSON representations, and nested partial reconstruction
  retain their documented limitations. Newly added Pydantic Settings source options
  are forwarded without requiring matching Confidantic signature changes.

  Copy, deepcopy, and mutate honor validation aliases and preserve settings-source
  provenance and explicit-field metadata for extras. Configurable equality compares
  stored fields and extras consistently with hashing. Empty and current-directory
  secondary paths resolve against the configured root. Direct CLI-source
  construction works with the default unset environment prefix.

  Generated factories isolate mutable defaults, preserve settings merging and union
  alternatives, resolve inherited constructor annotations, and retain the target's
  module metadata. Validate target compatibility, including compatible subclasses,
  and recognize callable typing objects as type selectors without invoking them.
  Finite recursive model values resolve while actual value cycles are rejected.
  Nested factories in sets initialize correctly on Python 3.14.

  Factory Make serialization uses the target import string, constructor fields, and
  canonical keyword names; ambiguous aliases and serializer failures propagate.
  Cloudpickle restores dynamic configuration/context classes and generated factory
  schemas while keeping ambient context local to each interpreter. Static typing
  supports specialized factory resolution and `Call`/`Make` annotations.
