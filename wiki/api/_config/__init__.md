# confidantic.\_config

This package joins the configuration implementation and re-exports its four public
symbols: `ConfigModelDict`, `ClassDefaultsSource`, `BaseConfig`, and `Factory`.
Applications should normally obtain them from `confidantic`.

## Initialization boundary

Import order brings in options and settings helpers before the model classes.
[`_options`](_options.md) registers the custom configuration keywords before
Pydantic creates `BaseConfig` subclasses. [`factory`](factory.md) depends on the
base model, while builder and resolver imports are deferred until public methods
need them. This arrangement supports schema construction during class creation.

The initializer owns no per-instance state and provides no customization hook.
Changes here should preserve symbol identity, avoid cycles, and keep Rich,
docstring-parser, YAML, and TOML writers out of core import paths. Import failures
from required dependencies propagate normally.

Evidence: [source](../../../src/confidantic/_config/__init__.py),
[root export tests](../../../tests/test_init.py), and
[fresh-process imports](../../../tests/integration/test_import_defaults.py).
See [configuration models](../../concepts/configuration-models.md),
[defining configuration](../../examples/defining-config.md), and
[the configuration index](README.md).
