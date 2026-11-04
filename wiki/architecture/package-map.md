# Package map

The public center is BaseConfig, a Pydantic Settings subclass with inheritance-aware
source resolution. Factory extends it with constructor-derived fields and explicit
object construction. Other modules adapt inputs or apply configuration to particular
runtime concerns.

## Ownership boundaries

| Behavior                                 | Owning implementation                                                                                              | Upstream collaborator                       |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| Public model operations and schema hooks | [base](../api/_config/base.md)                                                                                     | Pydantic BaseModel and BaseSettings         |
| Options, sources, defaults, provenance   | [\_options](../api/_config/_options.md), [\_settings](../api/_config/_settings.md)                                 | Settings source classes and merging         |
| Concrete nested baseline updates         | [\_nested](../api/_config/_nested.md)                                                                              | Model validation and field metadata         |
| CLI adaptation and suppression           | [\_cli](../api/_config/_cli.md)                                                                                    | CliSettingsSource                           |
| Factory validation and public methods    | [factory](../api/_config/factory.md)                                                                               | Pydantic core schemas                       |
| Factory generation and resolution        | [\_factory_build](../api/_config/_factory_build.md), [\_factory_resolution](../api/_config/_factory_resolution.md) | TypeAdapter, create_model, model rebuilding |
| Flexible input and executable directives | [annotations](../api/annotations.md), [utils](../api/utils.md)                                                     | Annotated validators and ImportString       |
| Activation and runtime ownership         | [context](../api/context.md), [configurable](../api/configurable.md)                                               | ContextVar and Python object protocols      |
| Filesystem and logging integration       | [paths](../api/paths.md), [logging](../api/logging.md)                                                             | pathlib and logging.config                  |
| Immutable mapping utility                | [types](../api/types.md)                                                                                           | Mapping and MappingProxyType                |

The [root initializer](../api/__init__.md) re-exports four configuration APIs and the
distribution version. An internal location does not make ClassDefaultsSource private;
its root export is part of the public interface. There is no plugin registry or
second internal model hierarchy for source collaborators.

## Following a change

For precedence changes, follow the [settings lifecycle](settings-lifecycle.md) and
test source ordering, aliases, nested updates, and provenance together. For factory
changes, follow the [factory lifecycle](factory-lifecycle.md) through schema generation,
copied defaults, CLI exposure, resolution, and serialization. The
[test layout](../../tests/README.md) mirrors implementation ownership; process-level
checks live in integration tests.

Optional modules sit at operation boundaries described in
[optional integrations](optional-integrations.md). State shared between call paths
has an explicit scope described in [state and isolation](state-and-isolation.md).
Start from [configuration concepts](../concepts/configuration-models.md) if the public
behavior is unfamiliar. Return to [architecture](README.md).
