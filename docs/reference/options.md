# Configuration options

Set options on `model_config = ConfigModelDict(...)` inside a configuration class.
[ConfigModelDict][confidantic.ConfigModelDict] extends Pydantic Settings' options;
it also accepts ordinary Pydantic model controls. These tables describe Confidantic's
base defaults. Subclasses and supported per-instance underscore options can change
them. Consult the [upstream SettingsConfigDict reference](https://docs.pydantic.dev/latest/api/pydantic_settings/#pydantic_settings.SettingsConfigDict)
for the full inherited catalog.

## Validation and updates

| Option                                | Base default | Effect                                                             |
| ------------------------------------- | ------------ | ------------------------------------------------------------------ |
| `frozen`                              | `True`       | Prevent field reassignment; nested mutable values can still change |
| `validate_default`                    | `True`       | Validate default values                                            |
| `nested_model_default_partial_update` | `True`       | Allow mappings to patch existing nested model baselines            |

Use [validated copy operations](../guide/settings.md#frozen-configuration) for updates.
Turning off nested partial updates changes concrete subtype and baseline retention;
see the [nested guide](../guide/nested-settings.md) for the per-call validation limitation.

## Environment, files, and secrets

| Option                 | Base default      | Effect                                                                       |
| ---------------------- | ----------------- | ---------------------------------------------------------------------------- |
| `env_prefix`           | `None`            | Disable process environment parsing at this class level; a string enables it |
| `env_nested_delimiter` | `"__"`            | Address nested fields from environment and dotenv names                      |
| `env_ignore_empty`     | `True`            | Ignore empty environment and dotenv values                                   |
| `env_parse_enums`      | `True`            | Accept enum member names from environment and dotenv input                   |
| `env_parse_none_str`   | `"null"`          | Interpret this text as `None`                                                |
| `env_file`             | `None`            | No explicit dotenv file                                                      |
| `env_file_discovery`   | `False`           | Opt into `find_dotenv()` when no file is selected                            |
| `dotenv_filtering`     | `"only_existing"` | Keep dotenv entries matching declared fields                                 |
| `secrets_dir`          | `None`            | No secret-file directory                                                     |

`env_prefix=""` enables unprefixed environment names. Disabling process environment
does not disable dotenv or secrets. Parent classes retain their own source options.
`env_prefix_target` controls whether the prefix applies to variable names, aliases,
or both; `case_sensitive` controls matching. These inherited controls are described
in the API reference.

Multiple dotenv files are ordered, with later files winning. `dotenv_filtering`
also accepts `"match_prefix"` to include otherwise unused prefixed entries, or
`None` to include unused entries regardless of prefix; model extra-field policy
then applies. `env_file_encoding` sets the encoding. `env_file_depth` requires
Pydantic Settings 2.16 or later, so do not assume it exists at the package's minimum
dependency version.

When discovery is enabled, `_env_file=None` requests discovery too. Disable
`env_file_discovery` to suppress that search. Override `find_dotenv()` for an
application-specific search location.

`json_file`, `yaml_file`, `toml_file`, and pyproject options configure their source
classes but do not register them. Use `settings_customise_sources` as shown in
[the files guide](../guide/files.md#use-a-toml-file-as-a-settings-source).

## Command-line options

| Option                          | Base default | Effect                                                                                    |
| ------------------------------- | ------------ | ----------------------------------------------------------------------------------------- |
| `cli_parse_args`                | `None`       | Automatic parsing disabled; `True` reads process arguments, a sequence supplies arguments |
| `cli_help`                      | `True`       | Include generated standard help; supplied custom parsers are not replaced                 |
| `cli_kebab_case`                | `True`       | Use hyphens in generated option names                                                     |
| `cli_implicit_flags`            | `False`      | Require explicit boolean values                                                           |
| `cli_ignore_unknown_args`       | `True`       | Ignore unknown arguments, supporting staged parsers                                       |
| `cli_avoid_json`                | `True`       | Prefer non-JSON syntax in generated help                                                  |
| `cli_hide_none_type`            | `True`       | Hide `None` types from help                                                               |
| `cli_show_env_vars`             | `False`      | Hide environment names from help                                                          |
| `cli_use_class_docs_for_groups` | `True`       | Use class documentation for argument groups                                               |
| `cli_parse_none_str`            | `"null"`     | Interpret this CLI text as `None`                                                         |

If `env_parse_none_str` is set, the settings CLI uses it for its null spelling.
`cli_prefix`, `cli_prog_name`, `cli_shortcuts`, and the other upstream options control
naming and presentation. Only the most-derived class parses CLI arguments.
Notebook-like runtimes suppress automatic parsing even for a configured sequence.

When constructing `CliSettingsSource` directly, enable `cli_show_env_vars` only with
an explicit string `env_prefix`, including `""` for unprefixed variables.
See [CLI examples](../guide/cli.md) for standalone and nested commands.

## Field documentation

| Option                             | Base default                           | Effect                                                                                      |
| ---------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------- |
| `use_attribute_docstrings`         | Enabled outside notebook-like runtimes | Extract field descriptions from source attribute docstrings                                 |
| `docstring_set_attributes_section` | `None`                                 | Enable replacement when an active `@attrs` marker exists; `False` disables replacement      |
| `docstring_style`                  | `None`                                 | Detect a marked Attributes section's style; `"numpy"` or `"google"` specifies it explicitly |

Explicit per-class extraction settings override the runtime-dependent default.
Explicit field descriptions take precedence over extracted attribute docstrings.
Marker replacement requires the `docstrings` extra; ordinary field description
extraction does not. See [descriptions and display](../guide/descriptions-and-display.md)
for examples and validation errors.
