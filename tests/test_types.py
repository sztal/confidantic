"""Tests for custom runtime types."""

import pickle
from typing import Any, cast

import pytest

from confidantic.types import FrozenDict


def test_frozen_dict_copies_and_exposes_mapping_contents() -> None:
    """FrozenDict snapshots a mapping and retains standard mapping behavior."""
    source = {"one": 1, "two": 2}
    frozen = FrozenDict(source)
    source["one"] = 10

    assert frozen == {"one": 1, "two": 2}
    assert list(frozen) == ["one", "two"]
    assert frozen["two"] == 2


def test_frozen_dict_rejects_mapping_mutation() -> None:
    """FrozenDict does not allow entries to be added or deleted."""
    frozen = cast(Any, FrozenDict({"one": 1}))

    with pytest.raises(TypeError):
        frozen["two"] = 2
    with pytest.raises(TypeError):
        del frozen["one"]


def test_frozen_dict_hash_is_order_independent_for_non_orderable_keys() -> None:
    """Equivalent mappings hash alike without comparing their heterogeneous keys."""
    first = FrozenDict({1: "one", "two": 2})
    second = FrozenDict({"two": 2, 1: "one"})

    assert first == second
    assert first == {"two": 2, 1: "one"}
    assert hash(first) == hash(second)


def test_frozen_dict_hash_rejects_unhashable_values() -> None:
    """FrozenDict only becomes hashable when every entry is hashable."""
    frozen: FrozenDict[str, list[object]] = FrozenDict({"items": []})

    with pytest.raises(TypeError):
        hash(frozen)


def test_frozen_dict_round_trips_through_pickle() -> None:
    """Pickle reconstruction preserves frozen mapping contents and behavior."""
    original = FrozenDict({"one": 1, "two": 2})
    restored = pickle.loads(pickle.dumps(original))

    assert isinstance(restored, FrozenDict)
    assert restored == original
    assert hash(restored) == hash(original)
