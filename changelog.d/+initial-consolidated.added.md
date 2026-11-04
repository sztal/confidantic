Initial release of Confidantic, with Pydantic Settings configuration and command-line interfaces.

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
