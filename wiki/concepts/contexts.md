# Context-local configuration

Use BaseContext for configuration that code within an execution context should be
able to retrieve without passing it through every function. Each concrete subclass
has independent activation storage. Its instances otherwise behave like BaseConfig.

## Construct, then activate

Constructing a context validates settings but does not make it current. `current()`
returns an existing activation or lazily constructs and retains a default instance.
`set(instance)` replaces the current activation persistently within that context.
`temporary(instance)` restores the previous activation on scope exit, including
when an exception occurs or there was no previous activation.

Activation checks the instance's class but does not revalidate its fields. It retains
the instance by reference. Use a validated copy when an override should differ from
the original without changing it.

## Sharing and process boundaries

ContextVar provides context-local bindings, not isolated copies of objects. New
asynchronous tasks inherit an activation by reference. Rebinding in one task does
not rebind another task, while mutation of the shared instance can affect both.
Nested mutable fields remain mutable even on a frozen configuration.

The class-to-variable registry is process-local. Serializing a context instance
transfers its data, not the ambient activation of its class in the sending process.
A fresh interpreter initializes its own registry and defaults. For worker input,
pass the desired instance explicitly and activate it in the worker if needed.

Use ordinary explicit configuration arguments when ambient lookup would make
ownership unclear. Contexts are useful for request or task scopes with a deliberate
entry/exit boundary.

See [context examples](../examples/contexts.md),
[context implementation](../api/context.md), and
[state lifetimes](../architecture/state-and-isolation.md). Return to [concepts](README.md).
