# Confidantic handbook

Confidantic combines Pydantic validation with inheritance-aware settings,
command-line interfaces, and explicit construction of configured objects.
This handbook explains how to use those facilities and how their implementation
fits together. The [public API reference](../docs/reference/api.md) supplies
signatures; these pages connect behavior, source, and tests.

## Use Confidantic

Start with [defining configuration](examples/defining-config.md), then
[environment and dotenv](examples/environment-and-dotenv.md),
[smart annotations](examples/smart-annotations.md), and [CLIs](examples/clis.md).
Continue with [factories](examples/factories.md) and
[object templates](examples/object-templates.md) to construct application components.
The [example guide index](examples/README.md) includes runtime integrations and
a smaller set of advanced recipes. Every guide links to an executable script.

## Understand its behavior

Read [configuration models](concepts/configuration-models.md),
[sources and inheritance](concepts/sources-and-inheritance.md), and
[nested configuration](concepts/nested-configuration.md) first.
The [concept index](concepts/README.md) covers the remaining abstractions.
The [architecture index](architecture/README.md) follows the settings and factory
lifecycles and identifies the lifetime of internal state.

## Modify its implementation

Begin with the [package map](architecture/package-map.md), then locate the owning
module in the [implementation reference](api/README.md). Each module page links
to source, behavioral tests, related concepts, and a practical example. File paths
inside that reference mirror the Python package, including private modules.

Before editing code, read [AGENTS.md](../AGENTS.md), [STYLE.md](../STYLE.md), and
the [test placement guide](../tests/README.md). Settings changes usually need
checks of inheritance, aliases, provenance, and nested validation; factory changes
also need checks of generated types and process serialization.

## Documentation boundaries

Concepts describe observable rules, architecture explains cooperating components,
and API pages explain implementation responsibilities. Runnable guides live in
[examples](../examples/); their smoke coverage lives in
[the integration tests](../tests/integration/test_examples.py).
The wiki is repository Markdown and is not included in the published documentation
build or default Markdown doctest paths. Check links and advertised commands when
editing it. Confirmed unresolved defects belong only in [BUGS.md](../BUGS.md).
