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
    Calling :func:`hash` raises :class:`TypeError` unless every key and value
    is hashable.
    """

    _data: Mapping[Key, Value]

    def __init__(self, values: Mapping[Key, Value]) -> None:
        object.__setattr__(self, "_data", MappingProxyType(dict(values)))

    def __getitem__(self, key: Key) -> Value:
        return self._data[key]

    def __iter__(self) -> Iterator[Key]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(frozenset(self.items()))

    def __reduce__(self) -> tuple[type[Self], tuple[dict[Key, Value]]]:
        return type(self), (dict(self._data),)
