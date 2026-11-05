"""Custom runtime types."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, Self, TypeVar

Key = TypeVar("Key")
Value = TypeVar("Value")


@dataclass(frozen=True, slots=True, init=False, eq=False)
class FrozenDict(Mapping[Key, Value], Generic[Key, Value]):
    """An immutable mapping with order-independent equality and hashing.

    Parameters
    ----------
    values
        Mapping whose entries are copied into this instance.

    Notes
    -----
    Immutability is shallow: values are retained by reference and may themselves
    be mutable. Iteration preserves the input mapping's iteration order, while
    equality follows :class:`collections.abc.Mapping` semantics and ignores order.
    Calling :func:`hash` raises :class:`TypeError` unless every key and value
    is hashable.
    """

    _data: Mapping[Key, Value]

    def __init__(self, values: Mapping[Key, Value]) -> None:
        object.__setattr__(self, "_data", MappingProxyType(dict(values)))

    def __getitem__(self, key: Key) -> Value:
        """Return the stored value, raising KeyError for an absent key."""
        return self._data[key]

    def __iter__(self) -> Iterator[Key]:
        """Iterate over keys in the input mapping's original iteration order."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return the number of stored entries."""
        return len(self._data)

    def __hash__(self) -> int:
        """Hash entries without ordering them; all keys and values must be hashable."""
        return hash(frozenset(self.items()))

    def __reduce__(self) -> tuple[type[Self], tuple[dict[Key, Value]]]:
        """Reconstruct from a plain dictionary when pickled, retaining the subclass."""
        return type(self), (dict(self._data),)
