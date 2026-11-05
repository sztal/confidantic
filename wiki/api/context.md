# confidantic.context

`BaseContext` adds activation to `BaseConfig`. Its public methods are `current`,
`set`, and `temporary`. Creating or validating an instance does not activate it.

## Registry and activation

The private `_context_var` helper finds a ContextVar for a concrete class in a
process-local `WeakKeyDictionary`. An `RLock` serializes registry access. Weak keys
avoid retaining classes solely because the registry knows them; the variable has
no default instance. Each subclass gets an independent entry.

`current()` returns the current activation or constructs and stores `cls()` on a
lookup miss. That construction uses ordinary settings sources. `set()` checks the
instance class and stores the value by reference without field revalidation.
`temporary()` saves a token and resets it in `finally`, restoring even a previously
unset state. Wrong activation types raise `TypeError`.

New asynchronous tasks inherit existing activations by reference. Replacing an
activation is context-local; mutating a shared configuration object is not.
Thread and task context behavior comes from Python's ContextVar machinery, not
from a Confidantic object-copying policy.

## When changing this module

Keep registry state outside model classes and generated schema callbacks. Serializing
a configuration or a local class must not carry ambient activation into a fresh
process. Preserve cleanup on exceptions, lazy construction, independent subclass
storage, and reference identity for accepted activations. Override settings policy
on a subclass rather than changing activation methods to perform extra validation.

Evidence: [source](../../confidantic/context.py),
[context tests](../../tests/test_context.py), and
[process serialization tests](../../tests/integration/test_serialization.py).
See [contexts](../concepts/contexts.md), [the guide](../examples/contexts.md),
and [the module index](README.md).
