# confidantic.\_config.\_factory_resolution

This module separates value traversal, model-type reconstruction, and factory
discovery. A public `model_resolve` or `instance` call owns one resolver; no resolver state survives
on the input model or generated schema.

## Value traversal

`_FactoryResolver.resolve()` constructs factory-class values with defaults, then
resolves constructor fields and calls their target. A root Factory can instead be
treated as a model by its inherited `model_resolve()` method. Target return values are
returned directly rather than traversed a second time.

`instance()` binds runtime arguments against the constructor signature and merges
them over configured fields before traversal. Missing inputs and invalid bindings
fail before dependencies are constructed. Omitted defaults remain untraversed;
only positional gaps needed to form the call are filled. Nested factories share
the active traversal state but receive no root runtime overrides.

Pydantic model fields and extras are recursively resolved, then validated through a
resolved model type using field names and aliases. Mappings become dictionaries;
lists, tuples, sets, and frozensets are rebuilt as their built-in types. Mapping keys
are traversed too. Arbitrary object attributes are not visited and those objects
remain shared.

`active` tracks identities on the current recursion path. Re-entering an active
value raises `ValueError`; a `finally` block removes identities on success or failure.
Repeated factories in sibling branches are constructed separately. This is cycle
detection, not memoization of constructed objects or preservation of aliasing.

## Resolved model types

`_ResolvedModelTypes` caches generated types by original class identity. It discovers
annotation dependencies, propagates which models require changes, and creates
replacement subclasses together using temporary ForwardRefs. A complete namespace
then allows self-referential and mutually recursive schemas to rebuild.

`resolve_annotation()` substitutes Factory target types through model references,
containers, unions, and Annotated values while preserving metadata. Field metadata
is copied before modification. Original classes are untouched. A forced reconstruction
can create a replacement even when annotations themselves are unchanged.

## Discovery and preservation rules

`contains_factory()` uses a separate visited set and tolerates cycles during discovery.
It does not evaluate defaults or inspect arbitrary objects. A BaseConfig with no
factory values can therefore return a shallow copy without traversal. Do not share
discovery's visited set with the resolver's active path.

Public methods own CLI suppression so it also surrounds constructors. Nested validation
and constructor exceptions propagate; the model-type cache is per call and need not
survive errors. Preserve type identity reuse within a call, separate construction of
repeated values, and container normalization when changing the implementation.

Evidence: [source](../../../confidantic/_config/_factory_resolution.py),
[resolution tests](../../../tests/_config/test_factory_resolution.py), and
[CLI suppression tests](../../../tests/_config/test_cli.py).
See [factory concepts](../../concepts/factories-and-templates.md),
[object templates](../../examples/object-templates.md), and [the index](README.md).
