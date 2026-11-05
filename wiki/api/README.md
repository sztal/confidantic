# Implementation reference

Each page maps directly to a Python module: replace `confidantic/` with `wiki/api/`
and `.py` with `.md`. Private paths identify implementation ownership; they do not
make every symbol in those modules private. Start with
[the package map](../architecture/package-map.md) for cross-module relationships.

| Module                                       | Responsibility                                                  |
| -------------------------------------------- | --------------------------------------------------------------- |
| [Package exports](__init__.md)               | Root public imports, distribution version, typing marker        |
| [Configuration internals](_config/README.md) | BaseConfig, factories, settings, and optional adapters          |
| [annotations](annotations.md)                | Paths, flexible string input, imports, and call directives      |
| [configurable](configurable.md)              | Configuration-owned runtime objects                             |
| [context](context.md)                        | Context-local activation                                        |
| [paths](paths.md)                            | Canonical paths and anchors                                     |
| [logging](logging.md)                        | Standard logging configuration                                  |
| [types](types.md)                            | FrozenDict                                                      |
| [utils](utils.md)                            | Runtime detection, import identifiers, and directive evaluation |

For an edit, locate the module, read its preservation rules, and follow its test
links. The [public reference](../../docs/reference/api.md) supplies full signatures;
these pages explain control flow and state. The [examples](../examples/README.md)
show how those contracts appear in application code.

Return to the [handbook](../README.md).
