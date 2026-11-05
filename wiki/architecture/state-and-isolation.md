# State and isolation

Confidantic uses short-lived collaborators and explicit context bindings. Different
state mechanisms solve different problems and must not be combined merely because
they all contain dictionaries or visited identities.

```text
process
  context-class registry --lock--> ContextVar per concrete class
                                      |
                         execution-context activation
                         temporary(): set / reset token

  model construction
    source builder and source values
    nested-update scope: push baseline map / restore enclosing map
    validated instance: provenance retained here

  model_resolve() call
    CLI suppression: set / reset token
    resolver: active value path + generated-type cache
    return: discard traversal state
```

The registry persists within a process; model-construction and resolver objects
belong to individual calls. A nested validation temporarily replaces the baseline
scope and restores its caller's scope afterward. CLI suppression spans multiple
validations because target constructors can create more settings models.

## Context-local bindings and shared objects

[BaseContext](../api/context.md) keeps its class registry outside models, guarded by
a lock and keyed weakly. ContextVars hold references to active instances. Task
inheritance therefore shares an instance until a task replaces its activation;
mutating the instance can cross that boundary. Token restoration must work on both
normal exit and exceptions.

## Three kinds of traversal state

Factory discovery uses a visited set to terminate scans of cyclic structures.
Resolution uses an active recursion path to reject actual value cycles while allowing
repeated sibling values. Type reconstruction caches by original class identity to
reuse generated models and rebuild mutually recursive annotations. Resolved target
objects are not cached. These structures intentionally have different semantics.

## Serialization and failure

Importable schema hooks and module-owned context variables keep transient state out
of dynamic model payloads. Fresh-process restoration transfers model data and supported
classes, not ambient activations or an in-progress validation. The
[integration tests](../../tests/integration/test_serialization.py) exercise cloudpickle
and worker transfers; this does not establish compatibility for old private layouts.

Cleanup must not depend on successful validation or construction. Nested scopes and
suppression reset tokens in finally blocks; active traversal identities are removed
when errors propagate. A failed call's generated-type cache can simply be discarded.

See [contexts](../concepts/contexts.md), [the context guide](../examples/contexts.md),
[\_nested](../api/_config/_nested.md), and
[\_factory_resolution](../api/_config/_factory_resolution.md).
Return to [architecture](README.md).
