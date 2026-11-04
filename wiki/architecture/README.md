# Architecture

These pages trace behavior across module boundaries. They complement the
[concepts](../concepts/README.md) and the source-shaped
[implementation reference](../api/README.md).

1. [Package map](package-map.md): public entry points and implementation ownership.
1. [Settings lifecycle](settings-lifecycle.md): from input sources to a validated model.
1. [Factory lifecycle](factory-lifecycle.md): from a constructor or template to objects.
1. [State and isolation](state-and-isolation.md): scopes, caches, and process boundaries.
1. [Optional integrations](optional-integrations.md): feature-local imports and failures.

Follow a lifecycle before changing its helper modules: source preparation and
field validation cooperate even though they live in different files. The same
applies to factory schema construction, generation, and resolution.
Return to the [handbook](../README.md) for usage-oriented routes.
