"""Tests for reusable Pydantic annotations."""

import sys

import pytest
from pydantic import BaseModel, ValidationError

from confidantic import Import


class ImportModel(BaseModel):
    """Model containing generic imported values."""

    imported_type: Import[type]
    imported_integer: Import[int]


def test_import_resolves_and_validates_strings() -> None:
    """String paths resolve before their generic type is validated."""
    model = ImportModel.model_validate(
        {
            "imported_type": "pathlib:Path",
            "imported_integer": "sys:maxsize",
        }
    )

    assert model.imported_type.__name__ == "Path"
    assert model.imported_integer == sys.maxsize


def test_import_accepts_already_resolved_values() -> None:
    """Values matching the generic parameter pass through unchanged."""
    model = ImportModel(imported_type=str, imported_integer=42)

    assert model.imported_type is str
    assert model.imported_integer == 42


def test_import_rejects_value_outside_generic_type() -> None:
    """The generic parameter constrains imported and direct values."""
    with pytest.raises(ValidationError, match="Input should be a type"):
        ImportModel.model_validate(
            {"imported_type": "sys:maxsize", "imported_integer": 42}
        )


def test_import_serializes_as_import_string() -> None:
    """Imported objects serialize to their import paths in JSON mode."""
    model = ImportModel(imported_type=str, imported_integer=42)

    assert model.model_dump(mode="json") == {
        "imported_type": "builtins.str",
        "imported_integer": 42,
    }
