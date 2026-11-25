# confidantic.configurable

`InstanceConfig` describes durable inputs. `Configurable` retains those inputs as
`config` and leaves runtime resources to subclasses. The configuration class is
the persistence boundary; the runtime object has no portable document API.

## Construction and association

`Configurable.__init_subclass__` associates a directly declared `Config` class
with its `Parent`. Merely inheriting `Config` does not rewrite this association;
multiple direct declarations of the same configuration class replace its parent.
`InstanceConfig.to_parent` requires a valid association directly on the concrete
configuration class and calls that parent with the configuration first.

Construction accepts a mapping, a Pydantic model, an existing configuration, or
no input. An existing instance of the correct Config class is reused when there
are no updates. Updates use validated `copy`; other models are dumped to mappings.
Keyword values override mapping entries before normal settings precedence applies.
Invalid Config declarations and unsupported inputs raise `TypeError`.

## Runtime state

Equality compares compatible runtime objects using their concrete configuration
type, declared fields, and extras. It omits private provenance and computed fields.
Hashing delegates to the configuration. Reconfiguration mutates the retained
configuration, so objects sharing it observe updates; derived caches are not rebuilt.

Copy protocols reconstruct the runtime object from a configuration copy. The
convenience `copy(**updates)` applies updates after that constructor, so transient
state may still reflect earlier values. Pickle stores only configuration and
restores it without calling the runtime constructor. Subclasses own restoration
of transient resources.

## When changing this module

Preserve direct-parent binding, reuse semantics, configuration-based equality,
and the ordering of constructor calls and updates. A subclass with required
runtime constructor arguments must accommodate the copy protocol itself.
Do not silently copy arbitrary runtime attributes or refresh resources during
reconfiguration: either change would alter the abstraction's lifecycle.

Evidence: [source](../../src/confidantic/configurable.py) and
[behavior tests](../../tests/test_configurable.py).
See [configured objects](../concepts/configured-objects.md),
[the runnable guide](../examples/configurable-objects.md), and
[all modules](README.md).
