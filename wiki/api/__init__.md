# confidantic

The package root is the supported import location for `BaseConfig`,
`ClassDefaultsSource`, `ConfigModelDict`, `Factory`, and `__version__`.
Its `__all__` defines that small surface; specialized integrations are imported
from their own modules. The four configuration symbols come through
[`_config`](_config/__init__.md), rather than being separate implementations.

## Import behavior

`__version__` is read from `importlib.metadata.version("confidantic")` at import
time. It describes the installed distribution and requires distribution metadata;
the module does not infer a version from a source file or suppress metadata errors.
The adjacent `py.typed` marker declares that the installed package supplies inline
typing information. It has no runtime initialization role.

There is no root-level registry or mutable configuration singleton. Core imports
must continue to work without the optional integrations installed. Adding a new
root import can accidentally move an optional dependency to this boundary.

## When changing this module

Keep re-export identity and `__all__` aligned, preserve metadata-derived versioning,
and check imports in a fresh interpreter. Prefer extending an owning module before
widening the root namespace; importing from a private file is not a new public API.

Evidence: [source](../../src/confidantic/__init__.py),
[export tests](../../tests/test_init.py), and
[optional-dependency tests](../../tests/integration/test_optional_dependencies.py).
Continue with [configuration models](../concepts/configuration-models.md) and
[defining configuration](../examples/defining-config.md), or return to
[the module index](README.md).
