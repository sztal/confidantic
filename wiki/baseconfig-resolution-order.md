# BaseConfig resolution order

## Goal

Describe the intended core behavior of `BaseConfig`: extend
`pydantic_settings.BaseSettings` with configuration resolution that is applied
independently at each level of a configuration class's MRO. This is a proposed
design; `BaseConfig` is not implemented in the current checkout.

## Decisions and findings

`BaseConfig` resolves a class completely before consulting its parent. At each
MRO level, sources are considered in this descending order:

1. Command-line arguments, when enabled.
1. Explicit initialization arguments.
1. Process environment variables.
1. Dotenv values.
1. Secret files.
1. Defaults declared by the current class.

This fixed chain includes only the file-backed sources that Pydantic Settings
provides by default: dotenv and secret files. Structured configuration files
are non-standard sources. A `BaseConfig` subclass must add JSON, TOML, YAML, or
`pyproject.toml` through `settings_customise_sources` and choose where each
source belongs in the precedence order. `BaseConfig` must not assign those
sources an implicit position.

The first value found for a field or nested key wins. Only values still absent
after the current class's defaults advance to the next parent in the MRO. A
default on a derived class therefore takes priority over any source that applies
only to a parent class.

```text
Resolve concrete config class
            |
            v
    CLI arguments
            |
            v
 Initialization arguments
            |
            v
 Environment variables
            |
            v
      Dotenv values
            |
            v
       Secret files
            |
            v
Current-class defaults
            |
            v
   All values resolved? ---- yes ---> Validated configuration
            |
            no
            |
            v
    Parent MRO class? ------- no ----> Missing required values
            |
            yes
            |
            +------------------------> Repeat from CLI arguments

Subclass extension rule:
JSON, TOML, YAML, and pyproject.toml sources may be inserted at any chosen
position in this chain through settings_customise_sources.
```

Pydantic Settings provides the machinery for an individual level, but not this
MRO-level traversal. Its documented default priority is CLI, when
`cli_parse_args` is enabled, then initialization arguments, environment,
dotenv, secrets, and defaults. A CLI source is topmost by default. JSON, TOML,
YAML, and `pyproject.toml` source classes are available but opt-in; a subclass
must add them through `settings_customise_sources`.

`settings_customise_sources` returns source callables in descending priority,
so the subclass controls whether a structured file overrides or falls back to
CLI, initialization, environment, dotenv, secrets, or another custom source.
Sources can also inspect the accumulated `current_state` and
`settings_sources_data`. Pydantic Settings merges source results deeply, which
lets lower-priority sources supply missing nested keys. The interaction between
that deep merge and per-MRO resolution must be specified and tested by
`confidantic`.

Supported file-backed sources are:

- Dotenv files, configured on the class with `env_file` or per instance with
  `_env_file`.
- Secret-file directories, configured with `secrets_dir` or per instance with
  `_secrets_dir`.
- JSON via `JsonConfigSettingsSource`.
- TOML via `TomlConfigSettingsSource`.
- YAML via `YamlConfigSettingsSource`.
- `pyproject.toml` via `PyprojectTomlConfigSettingsSource`.

Pydantic Settings has no `_json_file`, `_toml_file`, `_yaml_file`, or
`_pyproject_toml_file` initializer override. Structured file paths therefore
come from class `model_config` or from arguments passed by the subclass when it
constructs the source. Preserving this constraint keeps source registration and
priority explicit in the subclass.

## Validation

- Checked the [Pydantic Settings documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/#field-value-priority)
  for standard source priority and
  [source customization](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/#customise-settings-sources).
- Confirmed with Pydantic Settings 2.15 that only dotenv and secret paths have
  built-in instance initializer overrides; structured file sources do not.
- Confirmed this checkout has no `BaseConfig` implementation, so this page
  records intended behavior rather than current behavior.

## Follow-up

- Define how Pydantic Settings deep merging composes with MRO-level resolution.
- Define the public configuration for enabling and customizing CLI parsing.
- Implement focused tests for derived defaults overriding parent-only sources.
- Implement examples showing subclasses that place structured file sources at
  different priorities.
