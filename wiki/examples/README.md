# Runnable guides

Run the commands from the repository root after installing the development
environment with `uv sync --group dev --group docs --extra all`. For an application,
install `confidantic` and only the extras identified by its guide. Guides link
to runnable scripts; code blocks labelled as excerpts rely on that script's
earlier definitions. Supplemental snippets are labelled separately and are not
part of those scripts or their smoke tests. Run scripts and standalone snippets
in separate processes to isolate environment, logging, and context changes.

## Main functionality

1. [Define configuration](defining-config.md), inspect provenance, update values,
   and control display rows.
1. [Load environment and dotenv](environment-and-dotenv.md) with explicit source policies.
1. [Use smart annotations](smart-annotations.md) for flexible input.
1. [Define CLIs](clis.md), including nested commands.
1. [Nest configuration](nested-config.md) while retaining concrete defaults.
1. [Generate factories](factories.md) from constructors, with partial schemas
   and runtime overrides.
1. [Use object templates](object-templates.md) for nested dependencies and CLI options.
1. [Activate contexts](contexts.md) for scoped runtime settings.
1. [Define configurable objects](configurable-objects.md) and understand shared updates.
1. [Resolve paths](paths.md) with roots and anchors.
1. [Configure logging](logging.md).
1. [Serialize configuration](serialization.md) as mappings, JSON, YAML, and TOML.

## Advanced composition

The [advanced index](advanced/README.md) covers custom sources,
[factory annotation resolution](advanced/factory-annotations.md), runtime-selected
dependency types, and portable object graphs. Read the related main guide first.

The [example smoke tests](../../tests/integration/test_examples.py) list the
scripts they execute in temporary working directories. Existing guides that use `.env` locate
the fixture beside their script. Rich tables and temporary path names can vary;
the guides identify the stable values to inspect.

Return to the [handbook](../README.md), or read the underlying
[concepts](../concepts/README.md).
