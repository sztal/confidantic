# Configuration implementation

`BaseConfig` owns the public interface and dispatches to focused collaborators.
`Factory` builds on that interface without introducing an independent settings
system. Read the [settings lifecycle](../../architecture/settings-lifecycle.md)
or [factory lifecycle](../../architecture/factory-lifecycle.md) before following
individual private helpers.

| Module                                         | Responsibility                                            |
| ---------------------------------------------- | --------------------------------------------------------- |
| [Package exports](__init__.md)                 | Re-export public configuration APIs                       |
| [base](base.md)                                | BaseConfig and its Pydantic hook adapters                 |
| [\_options](_options.md)                       | ConfigModelDict and keyword registration                  |
| [\_settings](_settings.md)                     | MRO sources, defaults, provenance, and validation wrapper |
| [\_nested](_nested.md)                         | Model baselines and partial updates                       |
| [\_cli](_cli.md)                               | Parser selection, help policy, and resolution suppression |
| [factory](factory.md)                          | Factory schema and public construction methods            |
| [\_factory_build](_factory_build.md)           | Constructor inspection and recursive generation           |
| [\_factory_resolution](_factory_resolution.md) | Value traversal and resolved model types                  |
| [\_formats](_formats.md)                       | YAML and TOML codecs                                      |
| [\_info](_info.md)                             | Rich table construction and rendering                     |
| [\_docstrings](_docstrings.md)                 | Marker scanning and section replacement                   |
| [\_docstring_backend](_docstring_backend.md)   | Optional docstring composition and parsing                |

The directory is private, but `BaseConfig`, `Factory`, `ConfigModelDict`, and
`ClassDefaultsSource` are public through the root package. Return to
[all modules](../README.md) or the [handbook](../../README.md).
