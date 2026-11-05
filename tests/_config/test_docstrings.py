"""Attribute extraction and marked docstring sections through BaseConfig."""

from typing import Literal

import pytest
from docstring_parser import DocstringStyle, parse
from pydantic import Field

from confidantic import BaseConfig, ConfigModelDict
from confidantic._config._docstring_backend import _AttributeDocstringBackend


class DocumentedConfig(BaseConfig):
    """Configuration with a source-level field description.

    Attributes
    ----------
    @attrs
    """

    name: str
    """The name of the configuration."""


def _docstring_attributes(
    settings_cls: type[BaseConfig],
) -> list[tuple[str, str | None]]:
    parsed = parse(settings_cls.__doc__, style=DocstringStyle.NUMPYDOC)
    return [
        (item.arg_name, item.description)
        for item in parsed.params
        if item.args[0] == "attribute"
    ]


def test_model_info_uses_attribute_docstrings() -> None:
    """Source-level attribute docstrings populate field descriptions."""
    assert DocumentedConfig.model_fields["name"].description == (
        "The name of the configuration."
    )
    assert _docstring_attributes(DocumentedConfig) == [
        ("name", "The name of the configuration.")
    ]
    assert "The name of the configuration." in DocumentedConfig.model_info(
        output="string"
    )


def test_model_docstring_replaces_marker_and_preserves_other_sections() -> None:
    """Generated attributes replace the marker without losing other content."""

    class Config(BaseConfig):
        """Current summary.

        Attributes
        ----------
        @attrs

        Notes
        -----
        Keep this note.
        """

        primary: str = Field(description="Primary value.")
        secondary: int = Field(default=1, alias="SECONDARY")

    assert Config.__doc__ is not None
    parsed = parse(Config.__doc__, style=DocstringStyle.NUMPYDOC)

    assert parsed.short_description == "Current summary."
    assert _docstring_attributes(Config) == [
        ("primary", "Primary value."),
        ("secondary", None),
    ]
    assert "@attrs" not in Config.__doc__
    assert "SECONDARY" not in Config.__doc__
    assert any(
        item.args == ["notes"] and item.description == "Keep this note."
        for item in parsed.meta
    )


def test_model_docstring_marker_includes_inherited_fields() -> None:
    """Marked subclasses describe all effective model fields in order."""

    class ParentConfig(BaseConfig):
        """Parent configuration.

        Attributes
        ----------
        @attrs
        """

        inherited: str = Field(description="Inherited value.")

    class Config(ParentConfig):
        """Child configuration.

        Attributes
        ----------
        @attrs
        """

        direct: int = Field(description="Direct value.")

    assert _docstring_attributes(Config) == [
        ("inherited", "Inherited value."),
        ("direct", "Direct value."),
    ]
    assert _docstring_attributes(ParentConfig) == [("inherited", "Inherited value.")]


def test_model_docstring_generation_can_be_disabled() -> None:
    """The inherited opt-out leaves class docstrings unchanged."""
    original_docstring = "Original documentation.\n\nAttributes\n----------\n@attrs"

    class DisabledConfig(BaseConfig):
        __doc__ = original_docstring
        model_config = ConfigModelDict(
            docstring_set_attributes_section=False,
        )

        value: str = Field(description="Generated description.")

    class ChildConfig(DisabledConfig):
        """Child documentation."""

        child: int

    assert DisabledConfig.__doc__ == original_docstring
    assert ChildConfig.__doc__ == "Child documentation."


def test_model_docstring_without_marker_is_preserved_for_cli_models() -> None:
    """CLI-enabled models preserve docstrings without an opt-in marker."""
    original_docstring = (
        "Original documentation.\n\n"
        "Attributes\n"
        "----------\n"
        "handwritten\n"
        "    Keep this entry."
    )

    class Config(BaseConfig, cli_parse_args=True):
        __doc__ = original_docstring

        value: str = Field(description="Generated description.")

    assert Config.__doc__ == original_docstring


def test_model_docstring_generation_requires_a_docstring_by_default() -> None:
    """Undocumented models do not receive a generated attributes section."""

    class Config(BaseConfig):
        value: str = Field(description="Generated description.")

    assert Config.__doc__ is None


def test_model_docstring_without_marker_is_preserved() -> None:
    """Documented models need a marker before an Attributes section is added."""

    class Config(BaseConfig):
        """Summary without an attributes marker."""

        value: str = Field(description="Generated description.")

    assert Config.__doc__ == "Summary without an attributes marker."


def test_model_docstring_marker_is_replaced_for_cli_models() -> None:
    """CLI-enabled models replace the marker when they explicitly opt in."""

    class Config(BaseConfig, cli_parse_args=True):
        """CLI summary.

        Attributes
        ----------
        @attrs
        """

        value: str = Field(description="Generated description.")

    assert _docstring_attributes(Config) == [("value", "Generated description.")]


def test_fieldless_model_does_not_gain_an_attributes_section() -> None:
    """A model without fields keeps its original docstring unchanged."""

    class Config(BaseConfig):
        """Summary only."""

    assert Config.__doc__ == "Summary only."


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


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("terminal_newline", [False, True])
def test_leading_blank_lines_and_terminal_newline(
    style: Literal["numpy", "google"], newline: str, terminal_newline: bool
) -> None:
    """Leading blank lines and the final line ending survive replacement."""
    section = "\n".join("    " + line for line in _section(style).splitlines())
    original = "\n\n    Summary.\n\n" + section
    if terminal_newline:
        original += "\n"
    original = original.replace("\n", newline)

    class Config(BaseConfig):
        __doc__ = original
        value: int

    expected = original.replace("@attrs", "value" if style == "numpy" else "value:")
    assert Config.__doc__ == expected


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
    "prefix",
    [
        pytest.param("```python\n@attrs\n```", id="backtick-fence"),
        pytest.param("~~~python\n@attrs\n~~~", id="tilde-fence"),
        pytest.param("Example::\n\n    @attrs", id="literal-block"),
        pytest.param('>>> print("@attrs")\n@attrs', id="doctest"),
        pytest.param("Examples:\n    @attrs", id="examples"),
    ],
)
def test_active_marker_after_ignored_content(
    style: Literal["numpy", "google"], prefix: str
) -> None:
    """Scanning resumes after ignored content and preserves its literal markers."""
    if style == "numpy" and prefix.startswith("Examples:"):
        prefix = "Examples\n--------\n@attrs"
    prefix = "Summary.\n\n" + prefix + "\n\n"

    class Config(BaseConfig):
        __doc__ = prefix + _section(style)
        value: int

    generated = _section(style, "value" if style == "numpy" else "value:")
    assert Config.__doc__ == prefix + generated


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
    monkeypatch.setattr(
        _AttributeDocstringBackend, "compose", lambda *args, **kwargs: fragment
    )
    with pytest.raises(ValueError, match=message):

        class Config(BaseConfig):
            __doc__ = "Summary.\n\n" + _section("google")
            value: int


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
