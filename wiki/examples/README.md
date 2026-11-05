# Runnable guides

Run the commands from the repository root after installing the development
environment with `uv sync --group dev --group docs --extra all`. For an application,
install `confidantic` and only the extras identified by its guide. Each guide links
to the complete script; code blocks labelled as excerpts rely on that script's
earlier definitions. Run scripts in separate processes to isolate environment,
logging, and context changes.

## Main functionality

1. [Define configuration](defining-config.md), inspect provenance, and update values.
1. [Load environment and dotenv](environment-and-dotenv.md) with explicit source policies.
1. [Use smart annotations](smart-annotations.md) for flexible input.
1. [Define CLIs](clis.md), including nested commands.
1. [Nest configuration](nested-config.md) while retaining concrete defaults.
1. [Generate factories](factories.md) from constructors.
1. [Use object templates](object-templates.md) for nested dependencies and CLI options.
1. [Activate contexts](contexts.md) for scoped runtime settings.
1. [Define configurable objects](configurable-objects.md).
1. [Resolve paths](paths.md) with roots and anchors.
1. [Configure logging](logging.md).
1. [Serialize configuration](serialization.md) as mappings, JSON, YAML, and TOML.

## Advanced composition

The [advanced index](advanced/README.md) covers custom sources, runtime-selected
dependency types, and portable object graphs. Read the related main guide first.

The [example smoke tests](../../tests/integration/test_examples.py) execute every
script in a temporary working directory. Existing guides that use `.env` locate
the fixture beside their script. Rich tables and temporary path names can vary;
the guides identify the stable values to inspect.

Return to the [handbook](../README.md), or read the underlying
[concepts](../concepts/README.md).
