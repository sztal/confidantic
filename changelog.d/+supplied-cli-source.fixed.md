Fixed direct `CliSettingsSource` construction for `BaseConfig` subclasses with
the default `env_prefix=None`. Environment-variable names are now omitted from
CLI help by default. Set `cli_show_env_vars=True` with an explicit string
`env_prefix` (including `""` for unprefixed variables) to display them.
