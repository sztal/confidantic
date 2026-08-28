"""Tests for public annotation helpers."""

from typing import Annotated

from confidantic.annotations import get_proper_args


def test_get_proper_args_extracts_types_from_nested_annotations() -> None:
    """Concrete types are extracted from unions and annotated types."""
    annotation = list[Annotated[int | str, "metadata"]]

    assert list(get_proper_args(annotation)) == [int, str]
