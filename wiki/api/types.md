# confidantic.types

`FrozenDict` is a public Mapping implementation backed by a private mapping proxy.
It copies the supplied mapping's entries during initialization and exposes only
lookup, iteration, and length. Frozen dataclass fields prevent reassignment of
the backing attribute; stored values remain shared by reference.

## Equality, hashing, and persistence

Mapping equality is independent of insertion order. Iteration retains the input
order, while hashing uses a frozenset of items so equal dictionaries have equal
hashes regardless of order. Hashing raises `TypeError` if a key or value is
unhashable; shallow immutability does not guarantee hashability.

`__reduce__` reconstructs the concrete class from a plain dictionary. It avoids
attempting to pickle MappingProxyType itself and preserves FrozenDict subclasses.
Missing-key errors follow ordinary mapping behavior.

## When changing this module

Preserve the distinction between immutable entries and mutable referenced values.
Do not base equality or hashing on iteration order, and retain reconstruction
through the public constructor. There is no shared cache or registry. Subclasses
that change constructor requirements must account for the reduction protocol.

Evidence: [source](../../src/confidantic/types.py) and
[mapping tests](../../tests/test_types.py).
See [configuration models](../concepts/configuration-models.md) for related
freezing semantics and [defining configuration](../examples/defining-config.md)
for shallow/deep copying. Return to [all modules](README.md).
