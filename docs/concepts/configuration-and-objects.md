# Distinguish configuration from application objects

Configuration describes how something should behave. An application object does
the work: it may open a connection, hold a cache, or process requests. Keeping
those roles clear makes validation, testing, and persistence easier.

## Classes describe; instances hold values

A configuration class such as `AppConfig` describes fields and their rules.
`AppConfig()` creates one instance with validated values. `model_dump()` produces
a representation of those values; it does not save running resources.

Use the smallest abstraction that fits the task:

| Need                                                        | Starting point                      |
| ----------------------------------------------------------- | ----------------------------------- |
| Validate ordinary data without settings sources             | Pydantic `BaseModel`                |
| Read and validate application settings                      | Confidantic `BaseConfig`            |
| Derive settings from an existing annotated constructor      | `Factory`                           |
| Design an object that explicitly owns a configuration       | `InstanceConfig` and `Configurable` |
| Retrieve settings within a deliberate request or task scope | `BaseContext`                       |

## Factories and templates

A factory describes a construction that will happen later. The target class
supplies constructor fields; a template instance can supply concrete defaults.
The generated factory class is a configuration schema, and its instance contains
validated constructor inputs. Calling `model_resolve()` performs construction.

This separation lets an application validate inputs before opening resources.
It does not guarantee that construction succeeds: the target can still fail, for
example when opening a missing file. See [factories](../guide/factories.md) for the
complete sequence.

## Objects that own settings

`Configurable` takes the other direction: you explicitly design a configuration
class and associate it with a runtime class. The runtime object retains that
configuration, while handles and caches remain ordinary runtime attributes.
`config.to_parent()` builds the associated object.

Changing stored configuration does not automatically rebuild derived resources.
Design that transition explicitly; the [configured-object recipe](../recipes/configurable-objects.md)
explains construction, sharing, and updates.

## Documents describe values, not live state

For ordinary persistence, dump a configuration and validate the document with its
known concrete class when loading. A broad base-class annotation can omit
subclass-only fields unless you request `serialize_as_any=True`.

If a trusted document must choose concrete Python constructors, use
[object directives](../advanced/object-directives-and-portability.md). That adds
imports and calls, so it has different requirements from loading plain settings.
Neither ordinary documents nor a saved context instance transfer an active request
scope or an open runtime resource.

Continue with [state and lifetimes](state-and-lifetimes.md).
