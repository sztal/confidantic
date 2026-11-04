# Understand ownership and lifetimes

A validated value can still be shared. Before changing configuration, ask which
object owns it, who else can see it, and when it stops being active.

## Frozen fields and shared values

Freezing prevents field reassignment; it does not recursively freeze every object
inside a field. A list can remain mutable. A shallow `copy()` creates a new model
while sharing nested values; `deepcopy()` copies them recursively.

Copies with updates revalidate through settings construction. That can consult
sources again and rerun validators. `mutate()` changes the retained instance after
validation, so other owners of that same instance see the change. Do not mutate
an object while relying on its hash in a dictionary or set.

The [settings guide](../guide/settings.md#frozen-configuration) lists the precise
copy and private-state behavior.

## Context activation has a scope

A `BaseContext` instance is an ordinary configuration until it is activated.
`current()` retrieves an activation or creates and retains a default.
`temporary()` restores the previous activation on exit, even after an exception;
`set()` replaces it persistently within the current execution context.

The binding is local to an execution context, but its value is an object reference.
New asynchronous tasks inherit the current reference. Rebinding in one task does
not rebind another task; mutating their shared object can affect both. Prefer
validated copies for scoped changes, and pass settings explicitly when ambient
lookup would obscure ownership.

## Runtime resources have a separate lifetime

A `Configurable` can retain a supplied configuration instance by reference.
Reconfiguration changes that instance without repeating constructor setup. A cache
created by the constructor therefore needs its own refresh policy. See the
[recipe](../recipes/configurable-objects.md) before using copying as a resource-rebuild mechanism.

For worker processes, send configuration data and activate or construct objects
in the receiving process. Context activation stays process-local. Python object
serialization has different guarantees from a portable configuration document;
it is not a stable contract for internal layouts across versions.

The [context recipe](../recipes/contexts.md) shows a scoped override. The
[wiki's state and isolation discussion](https://github.com/sztal/confidantic/blob/master/wiki/architecture/state-and-isolation.md)
explains the deeper implementation boundaries.
