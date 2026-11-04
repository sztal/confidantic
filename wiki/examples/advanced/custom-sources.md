# Register a structured settings source

[custom_sources.py](../../../examples/custom_sources.py) needs core Confidantic.
TOML reading uses the standard library and does not require the TOML writer extra.

```console
uv run python examples/custom_sources.py
```

The script creates a temporary TOML file, sets `toml_file` in ConfigModelDict, and
registers a TomlConfigSettingsSource through `settings_customise_sources`.
The return statement below is an excerpt from that hook:

```python
return (
    init_settings,
    TomlConfigSettingsSource(settings_cls),
    env_settings,
    dotenv_settings,
    file_secret_settings,
)
```

## Make priority explicit

The sequence is descending priority. Initializer values can override the file,
while the file supplies values before later sources and class defaults. Merely
setting `toml_file` does not register a source. The example leaves process environment
disabled; setting a string env_prefix would enable the listed environment source.

Expected output:

```text
{'host': 'file.example.com', 'port': 9000}
{'host': 'caller.example.com', 'port': 9000}
```

The first model gets both values from TOML. The second supplies host explicitly and
retains the file's port. The script also asserts that host provenance names
TomlConfigSettingsSource and the concrete Config class.

Use `settings_cls` passed to the hook when constructing sources so each MRO level
gets the right options and provenance owner. JSON, YAML, and pyproject sources use
the same registration idea with their corresponding upstream source classes.
Bare callables are allowed but disable automatic provenance for the chain.

See [sources and inheritance](../../concepts/sources-and-inheritance.md),
[\_settings](../../api/_config/_settings.md), and [advanced guides](README.md).
