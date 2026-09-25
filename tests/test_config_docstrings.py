"""Attribute-section generation across supported docstring formats."""

from typing import Literal

import pytest
from docstring_parser import DocstringStyle, parse
from pydantic import Field

from confidantic import BaseConfig, ConfigModelDict
from confidantic._config import _docstrings


@pytest.fixture(params=["numpy", "google"])
def style(request: pytest.FixtureRequest) -> Literal["numpy", "google"]:
    return request.param


def _section(style: str, body: str = "@attrs") -> str:
    if style == "numpy":
        return "Attributes\n----------\n" + body
    return "Attributes:\n" + "\n".join("    " + line for line in body.splitlines())


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("cli", [False, True])
def test_generated_attributes(
    style: Literal["numpy", "google"], explicit: bool, cli: bool
) -> None:
    """Generated sections use effective field names and preserve surrounding text."""
    original = (
        "Summary.  \n\nCustom Before:\n    Keep this.  \n\n"
        + _section(
            style, "handwritten\n@attrs" if style == "numpy" else "handwritten:\n@attrs"
        )
        + "\n\nCustom After:\n    Keep this too.  \n\n"
    )

    if style == "numpy":
        original = original.replace("Custom After:", "Notes\n-----")

    class Parent(BaseConfig):
        inherited: str = Field(default="value", description="Inherited description.")

    class Config(Parent, cli_parse_args=cli):
        __doc__ = original
        model_config = ConfigModelDict(docstring_style=style if explicit else None)
        direct: str = Field(
            default="value", alias="DIRECT", description="First line.\nSecond line."
        )
        undescribed: int = 1

    assert Config.__doc__ is not None
    assert Config.__doc__.startswith(original[: original.index("Attributes")])
    assert Config.__doc__.endswith(
        original[original.index("\n\n", original.index("@attrs")) :]
    )
    selected = DocstringStyle.NUMPYDOC if style == "numpy" else DocstringStyle.GOOGLE
    attrs = [
        item
        for item in parse(Config.__doc__, style=selected).params
        if item.args[0] == "attribute"
    ]
    assert [
        (item.arg_name, " ".join((item.description or "").split())) for item in attrs
    ] == [
        ("inherited", "Inherited description."),
        ("direct", "First line. Second line."),
        ("undescribed", ""),
    ]
    assert "@attrs" not in Config.__doc__
    assert "handwritten" not in Config.__doc__


@pytest.mark.parametrize("marker", ["@attrs", "@attrs:"])
def test_google_markers(marker: str) -> None:
    """Google accepts both standalone spellings of the insertion marker."""

    class Config(BaseConfig):
        __doc__ = "Summary.\n\n" + _section("google", marker)
        value: str = Field(description="A value.")

    assert Config.__doc__ == "Summary.\n\nAttributes:\n    value: A value."


@pytest.mark.parametrize("indent", ["    ", "\t"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_original_layout(
    style: Literal["numpy", "google"], indent: str, newline: str
) -> None:
    """Replacement preserves original indentation and surrounding whitespace."""
    section = _section(style)
    original = "Summary.\n\n" + "\n".join(
        indent + line for line in section.splitlines()
    )
    original += (
        "\n" + indent + "\n" + indent + "Custom:\n" + indent * 2 + "Keep.  \n" + indent
    )
    custom = "Custom:\n" if style == "google" else "Custom\n" + indent + "------\n"
    original = original.replace("Custom:\n", custom).replace("\n", newline)

    class Config(BaseConfig):
        __doc__ = original
        value: str = Field(description="A value.")

    assert Config.__doc__ is not None
    prefix, _ = original.split(indent + section.splitlines()[0], 1)
    assert Config.__doc__.startswith(prefix + indent + section.splitlines()[0])
    assert Config.__doc__.endswith(
        newline
        + indent
        + newline
        + indent
        + custom.rstrip("\n").replace("\n", newline)
        + newline
        + indent * 2
        + "Keep.  "
        + newline
        + indent
    )


@pytest.mark.parametrize("disabled", [False, True])
def test_inherited_configuration(
    style: Literal["numpy", "google"], disabled: bool
) -> None:
    """Expected format and the generation opt-out inherit normally."""

    class Parent(BaseConfig):
        model_config = ConfigModelDict(
            docstring_style=style, docstring_set_attributes_section=not disabled
        )

    original = "Summary.\n\n" + _section(style)

    class Child(Parent):
        __doc__ = original
        value: int

    assert Child.model_config["docstring_style"] == style
    assert (Child.__doc__ == original) is disabled

    opposite = "google" if style == "numpy" else "numpy"

    class Override(Parent):
        __doc__ = "Summary.\n\n" + _section(opposite)
        model_config = ConfigModelDict(docstring_style=None)
        value: int

    assert Override.model_config["docstring_style"] is None


@pytest.mark.parametrize(
    "original",
    [
        "Summary mentions @attrs in prose.",
        "Summary.\n\nExamples:\n    @attrs",
        "Summary.\n\nExamples\n--------\n@attrs",
        "Summary.\n\nExample::\n\n    @attrs",
        'Summary.\n\n>>> print("@attrs")\n@attrs',
        "Summary.\n\n```python\n@attrs\n```",
        "Summary.\n\nAttributes\n----------\nvalue\n    A literal marker: @attrs\n    @attrs",
        "Summary.\n\nAttributes:\n    value:\n        @attrs",
        "Summary.\n\nAttributes:\n    value: Literal::\n\n        @attrs",
    ],
)
def test_non_insertion_markers_are_unchanged(original: str) -> None:
    """Prose, examples, and nested literal markers do not request generation."""

    class Config(BaseConfig):
        __doc__ = original
        value: int

    assert Config.__doc__ == original


@pytest.mark.parametrize(
    "original",
    [
        "Summary.\n\n@attrs",
        "Summary.\n\nAttributes\n@attrs",
        "Summary.\n\nAttributes:\n@attrs",
        "Summary.\n\nAttributes\n----------\n@attrs:",
        "Summary.\n\nAttributes\n---\n@attrs",
        "Summary.\n\nAttributes\n----------\n    @attrs",
        "Summary.\n\nAttributes:\n    @attrs\n    @attrs:",
        "Summary.\n\nAttributes\n----------\n@attrs\n@attrs",
        "Summary.\n\nNotes:\n    @attrs",
    ],
)
def test_invalid_marked_inputs_raise(original: str) -> None:
    """Malformed standalone insertion requests fail at class creation."""
    with pytest.raises(ValueError, match="Config:"):

        class Config(BaseConfig):
            __doc__ = original
            value: int


@pytest.mark.parametrize("other", ["numpy", "google"])
def test_duplicate_sections_raise(
    style: Literal["numpy", "google"], other: str
) -> None:
    """Duplicate sections are rejected even when the parser collapses them."""
    with pytest.raises(ValueError, match="exactly one Attributes"):

        class Config(BaseConfig):
            __doc__ = (
                "Summary.\n\n" + _section(style) + "\n\n" + _section(other, "manual")
            )
            model_config = ConfigModelDict(docstring_style=style)
            value: int


def test_expected_format_conflict(style: Literal["numpy", "google"]) -> None:
    """Explicit format selection validates rather than converts the input."""
    with pytest.raises(ValueError, match="does not match docstring_style"):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\n" + _section(
                "google" if style == "numpy" else "numpy"
            )
            model_config = ConfigModelDict(docstring_style=style)
            value: int


def test_invalid_generated_docstring_raises() -> None:
    """Parsing the complete result detects malformed recognized sections."""
    with pytest.raises(ValueError, match="invalid generated google docstring"):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\nAttributes:\n    @attrs\n\nArgs:\n    invalid entry"
            value: int


@pytest.mark.parametrize(
    "fragment, message",
    [
        ("Attributes:\n    other: Wrong field.", "do not match model fields"),
        (
            "Attributes:\n    value:\n\nAttributes:\n    value:",
            "exactly one Attributes",
        ),
        ("Attributes:\n    @attrs:", "still contains an @attrs"),
    ],
)
def test_candidate_validation(
    monkeypatch: pytest.MonkeyPatch, fragment: str, message: str
) -> None:
    """The candidate is checked independently of composer success."""
    monkeypatch.setattr(_docstrings, "compose", lambda *args, **kwargs: fragment)
    with pytest.raises(ValueError, match=message):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\n" + _section("google")
            value: int


def test_marked_fieldless_numpy() -> None:
    """A valid empty NumPy section retains its heading."""

    class Config(BaseConfig):
        __doc__ = "Summary.\n\n" + _section("numpy")

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------"


def test_marked_fieldless_google() -> None:
    """An empty Google section fails the required parser validation."""
    with pytest.raises(ValueError, match="invalid generated google docstring"):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\n" + _section("google")


@pytest.mark.parametrize("trailing", ["", "  "])
def test_numpy_marker_whitespace(trailing: str) -> None:
    """Whitespace around a standalone marker does not change its meaning."""

    class Config(BaseConfig):
        __doc__ = (
            "Summary.\n\nAttributes\n----------" + trailing + "\n@attrs" + trailing
        )
        value: int

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------\nvalue"


def test_numpy_typed_handwritten_entry() -> None:
    """Typed handwritten entries belong to the section being replaced."""

    class Config(BaseConfig):
        __doc__ = (
            "Summary.\n\nAttributes\n----------\nmanual : int\n    Old entry.\n@attrs"
        )
        value: int

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------\nvalue"


def test_custom_numpy_heading_with_punctuation() -> None:
    """Opaque custom headings are treated literally during validation."""
    suffix = "\n\nCustom (details)\n----------------\nKeep this content."

    class Config(BaseConfig):
        __doc__ = "Summary.\n\nAttributes\n----------\n@attrs" + suffix
        value: int

    assert Config.__doc__ == "Summary.\n\nAttributes\n----------\nvalue" + suffix
