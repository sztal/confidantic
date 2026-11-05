# Sources and inheritance

Configuration resolution combines two orders: source priority within a class and
the concrete-to-parent Python C3 MRO. With ordinary enabled sources, the concrete
class contributes CLI, initializer, environment, dotenv, secrets, and directly
declared defaults. Parent levels contribute their sources and defaults afterward,
without parsing CLI again. Customization can change source ordering within a level.

## Consequences of the ordering

A child default can outrank a parent environment value. A required child field
without a default does not introduce a default barrier. Nested mappings can receive
missing keys from later sources; scalar and sequence values are replaced according
to priority. Sources still execute even when earlier sources filled every field,
so malformed lower-priority source input can still fail construction.

Process environment is disabled by default through `env_prefix=None`. Set a string
prefix, including an empty string for unprefixed variables, to enable it. Disabling
that source does not disable dotenv or secrets, and parent levels retain their own
configuration. Aliases and prefix-target policy affect external names; model fields
keep canonical names.

## Files and customization

Dotenv loading is explicit unless `env_file_discovery=True`. Multiple configured
files are ordered, with later files overriding earlier ones. Discovery runs once
per source build when no file is selected. Explicit `_env_file=None` also requests
discovery when enabled; disable discovery to suppress it. Override `find_dotenv`
for application-specific search locations: the default script search starts at
the helper's source directory, not necessarily the application's directory.

Structured JSON, YAML, TOML, and pyproject sources require registration through
`settings_customise_sources`. Setting a filename alone does not install a source.
The returned sequence defines descending priority at that MRO level.

## Provenance

`model_field_sources` maps canonical names to `(source_class, configuration_class)`.
It identifies the first source establishing a top-level field; it does not describe
every nested key's origin. Extras and computed fields are omitted. A bare callable
source disables automatic provenance for the chain. Default factories are attributed
to ClassDefaultsSource even though Pydantic evaluates their actual values later.

See [environment and dotenv](../examples/environment-and-dotenv.md),
[custom sources](../examples/advanced/custom-sources.md), and
[source implementation](../api/_config/_settings.md). Return to [concepts](README.md).
