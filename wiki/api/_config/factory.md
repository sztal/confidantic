# confidantic.\_config.factory

`Factory[T]` is the public constructor-derived configuration abstraction. This module
owns target-aware schemas and the public methods; generation and traversal live in
separate collaborators imported after the Factory class exists.

## Schema behavior

`_factory_target` obtains the concrete or generic target; `_is_factory_type` recognizes
factory classes. Generic specializations build a concrete schema through `model_from`
and the shared settings wrapper. Specialized schema dictionaries are copied so
serialized schema state can be restored independently.

Lax validation retains compatible factory classes/instances, validates mappings,
and converts compatible target classes or instances into generated factories.
Existing compatible factories bypass field revalidation. Strict validation rejects
factory class values and target conversions while accepting mapping input and
compatible factory instances. Both branches enforce target compatibility.
Mapping errors retain normal model diagnostics; conversion TypeError/ValueError
become the factory validation error.

## Public construction methods

`model_from(source, ...)` selects the target and optional template. Constructor
arguments accompanying a type construct a template first; arguments accompanying
an instance are rejected. With a type and no arguments, the target is not constructed.
A specialized Factory enforces target compatibility before delegating to
[\_factory_build](_factory_build.md). The returned class is not registered as an
importable module attribute.

`instance_from(source, **kwargs)` generates a model and instantiates it with those
configuration inputs. They are subject to normal settings precedence. Recursive
generation and constructor arguments use `model_from` followed by instantiation.

`model_resolve()` delegates to [\_factory_resolution](_factory_resolution.md) under
CLI suppression. Only `factory_fields` are forwarded as constructor keyword arguments;
additional fields on a Factory subclass are excluded. Every call can execute target
constructors. Updates must be made before resolution.

## Serialization and preservation rules

The named `_serialize_factory` callback delegates instance serialization and preserves
class values. BaseConfig's Make serializer records the target and canonical constructor
keywords rather than the generated class. Keep that division of responsibility.

Preserve strict/lax differences, generic compatibility, and schema creation during
root class initialization. Do not capture builders/resolvers in schemas or assume
generated classes are automatically importable. Factory fields are not revalidated
before target calls: unchecked construction/copying can carry invalid scalar values.
Constructor errors and traversal-cycle errors propagate.

Evidence: [source](../../../confidantic/_config/factory.py),
[public factory tests](../../../tests/_config/test_factory.py), and
[serialization tests](../../../tests/integration/test_serialization.py).
See [factory concepts](../../concepts/factories-and-templates.md),
[the introductory guide](../../examples/factories.md), and [the index](README.md).
