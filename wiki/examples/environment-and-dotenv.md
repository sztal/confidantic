# Load environment and dotenv settings

Core Confidantic supports these sources. Process environment requires an explicit
string prefix; dotenv files are configured separately. Run:

```console
uv run python examples/basic.py
uv run python examples/env_files.py
```

[basic.py](../../examples/basic.py) loads the `.env` fixture beside the script.
It verifies `name="example"` and `number=1`, overrides the name through an environment
variable, then uses explicit initializer values. Its child class demonstrates that
a child default can outrank parent-level input.

## Order multiple files explicitly

[env_files.py](../../examples/env_files.py) creates its fixtures in a TemporaryDirectory.
This excerpt uses `shared_file` and `local_file` established earlier in that script:

```python
class MultipleFilesConfig(BaseConfig):
    """Configuration loaded from ordered dotenv files."""

    model_config = ConfigModelDict(
        env_file=(shared_file, local_file),
        env_prefix="MULTIPLE_",
    )

    name: str
```

The later file wins, producing `name="from-local-file"`. The single-file case produces
`"from-single-file"`; the application-specific discovery case produces `"from-discovery"`.

## Choose discovery policy

The discovery class enables `env_file_discovery` and overrides `find_dotenv()` to
return a known application path. Use that pattern when the application's directory
should determine the search. Default discovery does not necessarily start there.
An explicit `_env_file=None` still requests discovery when discovery is enabled.

Environment values normally outrank dotenv, and initializer values outrank both;
enabled CLI input outranks initializer values. Apply that ordering within each MRO
level rather than treating every environment source as globally stronger than defaults.
Secret files follow dotenv in the standard order and use `secrets_dir` or its
initializer override.

Read [sources and inheritance](../concepts/sources-and-inheritance.md) and
[\_settings](../api/_config/_settings.md). For a structured file source, continue to
[custom sources](advanced/custom-sources.md). Return to [all guides](README.md).
