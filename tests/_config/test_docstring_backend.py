"""Composition and parser validation of generated Attributes sections."""

import pytest

from confidantic import BaseConfig


def test_invalid_generated_docstring_raises() -> None:
    """Parsing the complete result detects malformed recognized sections."""
    with pytest.raises(ValueError, match="invalid generated google docstring"):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\nAttributes:\n    @attrs\n\nArgs:\n    invalid entry"
            value: int


def test_marked_fieldless_numpy() -> None:
    """A valid empty NumPy section retains its heading."""

    class Config(BaseConfig):
        __doc__ = "Summary.\n\nAttributes\n----------\n@attrs"

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------"


def test_marked_fieldless_google() -> None:
    """An empty Google section fails the required parser validation."""
    with pytest.raises(ValueError, match="invalid generated google docstring"):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\nAttributes:\n    @attrs"


def test_custom_numpy_heading_with_punctuation() -> None:
    """Opaque custom headings are treated literally during validation."""
    suffix = "\n\nCustom (details)\n----------------\nKeep this content."

    class Config(BaseConfig):
        __doc__ = "Summary.\n\nAttributes\n----------\n@attrs" + suffix
        value: int

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------\nvalue" + suffix
