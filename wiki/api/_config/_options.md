# confidantic.\_config.\_options

`ConfigModelDict` is a public TypedDict extending Pydantic Settings' configuration
dictionary. Most described options are inherited. Confidantic declares four extra
keys: `docstring_set_attributes_section`, `docstring_style`, `env_file_discovery`,
and `cli_help`.

## Registration and consumption

At import time, `_CUSTOM_CONFIG_KEYS` subtracts upstream annotations from the local
annotations and registers the remaining names with Pydantic's configuration-key
set. This supports class-definition keywords before BaseConfig subclasses exist.
The settings wrapper also uses the set to extract underscore-prefixed per-call
overrides without changing model configuration globally.

Defaults live on BaseConfig. Environment prefix None disables that level's normal
process environment source, while an empty prefix enables unprefixed input. Dotenv
and secrets remain separate. Structured-file options configure a source but do not
register it; callers must use `settings_customise_sources`.

This module's runtime effect is keyword registration, not configuration validation
or parser construction. The consumers own malformed option errors. Version-dependent
upstream options must remain documented as such; the TypedDict is not a guarantee
that every installed upstream version implements every described feature.

## When changing this module

Keep new custom keys distinguishable from upstream keys and provide handling in the
owning collaborator. Check model-level, class-keyword, and per-instance behavior.
Preserve import ordering: registration must happen before model class creation.

Evidence: [source](../../../src/confidantic/_config/_options.py) and
[option tests](../../../tests/_config/test_options.py).
See [configuration models](../../concepts/configuration-models.md),
[environment examples](../../examples/environment-and-dotenv.md), and [the index](README.md).
