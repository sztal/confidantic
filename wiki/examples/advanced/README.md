# Advanced composition

These recipes combine the main facilities rather than introducing a separate
configuration system. Their complete scripts remain small enough to run locally.

1. [Custom sources](custom-sources.md): place a structured document at an explicit
   point in settings precedence. Read [environment and dotenv](../environment-and-dotenv.md) first.
1. [Dynamic template CLIs](dynamic-template-clis.md): select dependency classes
   before generating their options. Read [object templates](../object-templates.md) first.
1. [Portable object graphs](portable-object-graphs.md): restore concrete types
   through trusted directives. Read [serialization](../serialization.md) first.

Runtime-selected classes need compatible constructors; portable directives need
importable targets. The recipes explain these conditions at the point of use.
Return to [all examples](../README.md) or the [handbook](../../README.md).
