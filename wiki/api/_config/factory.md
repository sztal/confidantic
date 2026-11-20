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
configuration inputs, subject to normal settings precedence. It also accepts
the annotation and field-selection generation options below. Recursive generation
and constructor arguments use `model_from` followed by instantiation.

Both methods accept `__types_namespace__` to supply annotation names and
`__strict__` to control unresolved or missing annotations. Default strict
generation omits unannotated parameters and rejects unresolved names; permissive
generation uses `Any` for those fields. Generated models retain this policy for
rebuilds and target conversions. These options are independent of strict/lax
validation described above. See the
[annotation guide](../../examples/advanced/factory-annotations.md).

`instance(*args, **kwargs)` delegates to [\_factory_resolution](_factory_resolution.md)
under CLI suppression. Runtime bindings override configured `factory_fields` before
recursive traversal. Additional model fields are excluded. Runtime values receive
no additional field validation; use `copy(...).instance()` for validated updates.

`model_resolve()` is inherited from BaseConfig and preserves the root model while
constructing nested factories. Factory instances remain non-callable, including
when supplied to `Make[Factory[T]]` or `Call[Factory[T]]` validation.

`__include__` and `__exclude__` select root constructor fields using name sets,
name predicates, or (resolved annotation, name) predicates. They are mutually
exclusive, persist through target conversions, and do not propagate recursively.
Excluded required inputs must be supplied to `instance()`.

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
