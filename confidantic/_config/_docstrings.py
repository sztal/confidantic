"""Replace marked attribute sections without rewriting surrounding text.

A line-based scan locates sections and active markers while retaining their
original line indices. Only the replacement section is composed; the complete
result is then parsed to validate its meaning independently of the layout scan.
"""

import re
from dataclasses import dataclass
from typing import Literal

from docstring_parser import (
    Docstring,
    DocstringParam,
    DocstringStyle,
    ParseError,
    compose,
    parse,
)
from docstring_parser.numpydoc import NumpydocParser, Section

_Style = Literal["numpy", "google"]
_STYLES = {"numpy": DocstringStyle.NUMPYDOC, "google": DocstringStyle.GOOGLE}


@dataclass(frozen=True)
class _SectionSpan:
    """Section boundaries as zero-based line indices, with an exclusive end."""

    title: str
    style: _Style
    header_start: int
    body_start: int
    end: int


class _LiteralNumpySection(Section):
    """Treat a custom NumPy section as text rather than additional attributes."""

    @property
    def title_pattern(self) -> str:
        # Custom titles may contain regex syntax, such as parentheses.
        return rf"^({re.escape(self.title)})[ \t]*\n{'-' * len(self.title)}[ \t]*$"


def _scan_docstring(text: str) -> tuple[list[str], list[_SectionSpan], list[int]]:
    """Locate section boundaries and standalone insertion markers.

    Returns
    -------
    lines : list[str]
        Dedented scan view with tabs expanded and line endings removed. Its
        indices remain aligned with the original text, including blank lines.
    sections : list[_SectionSpan]
        NumPy and Google sections in heading order, with exclusive end indices.
    active_markers : list[int]
        Marker line indices outside examples and literal content. These may
        lie outside Attributes; the caller validates insertion requests.
    """
    # Keep line indices aligned with the original, unlike cleandoc(), which
    # removes leading/trailing empty lines. Expand tabs only in the scan view.
    lines = text.expandtabs().splitlines()
    margin = min(
        (len(line) - len(line.lstrip()) for line in lines[1:] if line.strip()),
        default=0,
    )
    lines = [line.lstrip() if i == 0 else line[margin:] for i, line in enumerate(lines)]

    # Collect headings and markers outside literal content. Literal blocks end
    # at dedentation, fences at the next fence, and doctests at a blank line.
    headings: list[tuple[str, _Style, int, int]] = []
    markers: list[int] = []
    literal_indent: int | None = None
    fenced = False
    doctest = False
    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            doctest = False
            continue
        indent = len(line) - len(line.lstrip())
        if literal_indent is not None:
            if indent > literal_indent:
                continue
            literal_indent = None
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        if stripped.startswith(">>>"):
            doctest = True
        if doctest:
            continue
        if stripped.endswith("::"):
            literal_indent = indent
            continue
        if indent == 0:
            if (
                line_index + 1 < len(lines)
                and len(lines[line_index + 1].rstrip()) >= 3
                and set(lines[line_index + 1].rstrip()) == {"-"}
            ):
                headings.append((stripped, "numpy", line_index, line_index + 2))
            elif stripped.endswith(":") and stripped not in {"@attrs:"}:
                headings.append((stripped[:-1], "google", line_index, line_index + 1))
        if stripped in {"@attrs", "@attrs:"}:
            markers.append(line_index)

    # NumPy sections end at the next NumPy heading. Google sections end at
    # any heading or unindented content.
    sections: list[_SectionSpan] = []
    for heading_index, (title, style, header_start, body_start) in enumerate(headings):
        end = next(
            (
                next_header_start
                for _, next_style, next_header_start, _ in headings[heading_index + 1 :]
                if style == "google" or next_style == "numpy"
            ),
            len(lines),
        )
        if style == "google":
            end = next(
                (
                    line_index
                    for line_index in range(body_start, end)
                    if lines[line_index] and not lines[line_index][0].isspace()
                ),
                end,
            )
        sections.append(_SectionSpan(title, style, header_start, body_start, end))

    # Section context distinguishes insertion requests from example text and
    # markers nested within an entry's description.
    active_markers: list[int] = []
    for marker_index in markers:
        section = next(
            (
                candidate
                for candidate in sections
                if candidate.body_start <= marker_index < candidate.end
            ),
            None,
        )
        if section is not None:
            if section.title.lower() in {"example", "examples"}:
                continue
            entry_indent = min(
                (
                    len(line) - len(line.lstrip())
                    for line in lines[section.body_start : section.end]
                    if line.strip()
                ),
                default=0,
            )
            marker = lines[marker_index]
            if len(marker) - len(marker.lstrip()) > entry_indent:
                continue
        active_markers.append(marker_index)
    return lines, sections, active_markers


def replace_attributes(
    text: str,
    *,
    fields: dict[str, str | None],
    style: _Style | None,
    class_name: str,
) -> str:
    """Replace a marked Attributes section with model field documentation.

    Parameters
    ----------
    text : str
        Original class docstring. A standalone ``@attrs`` marker requests
        replacement of the entire Attributes section; Google sections also
        accept ``@attrs:``. Markers in examples or literal content are ignored.
    fields : dict[str, str | None]
        Effective model field names and descriptions, in output order.
    style : {"numpy", "google"} or None
        Expected input format, or None to detect it from the Attributes
        section. An explicit style validates the format without converting it.
    class_name : str
        Class name prefixed to validation error messages.

    Returns
    -------
    str
        Docstring with the generated section, preserving surrounding text and
        using the original heading's indentation and LF/CRLF convention. Returns the
        original text unchanged when no active marker is present.

    Raises
    ------
    ValueError
        If the marked section is invalid, its style conflicts with the expected
        format, or the completed docstring fails structural or parser validation.
        Empty marked Google sections fail validation; NumPy permits them.
    """
    lines, sections, active_markers = _scan_docstring(text)
    if not active_markers:
        return text

    def fail(reason: str) -> ValueError:
        return ValueError(f"{class_name}: {reason}")

    # Validate the insertion request before composing any replacement text.
    attributes = [section for section in sections if section.title == "Attributes"]
    if len(attributes) != 1:
        raise fail("expected exactly one Attributes section")
    section = attributes[0]
    if (
        len(active_markers) != 1
        or not section.body_start <= active_markers[0] < section.end
    ):
        raise fail("expected one @attrs marker inside Attributes")
    marker = lines[active_markers[0]]
    if section.style == "numpy" and (
        marker.rstrip() != "@attrs"
        or lines[section.header_start + 1].rstrip() != "----------"
    ):
        raise fail("invalid NumPy @attrs marker")
    if style is not None and style != section.style:
        raise fail(f"Attributes section does not match docstring_style={style!r}")

    # Compose only the Attributes section so other sections keep their layout.
    parser_style = _STYLES[section.style]
    generated = Docstring(style=parser_style)
    generated.meta = [
        DocstringParam(
            args=["attribute", name],
            description=description,
            arg_name=name,
            type_name=None,
            is_optional=None,
            default=None,
        )
        for name, description in fields.items()
    ]
    fragment = compose(generated, style=parser_style, indent="    ").strip("\n")
    # Composers omit empty sections; retain the header and let validation
    # determine whether the parser accepts an empty Attributes section.
    if not fragment:
        fragment = (
            "Attributes\n----------" if section.style == "numpy" else "Attributes:"
        )

    # Splice original lines, leaving trailing blank lines outside the replaced
    # span so their whitespace survives exactly.
    original_lines = text.splitlines(keepends=True)
    replacement_end = section.end
    while (
        replacement_end > section.body_start and not lines[replacement_end - 1].strip()
    ):
        replacement_end -= 1
    header = original_lines[section.header_start]
    prefix = header[: len(header) - len(header.lstrip(" \t"))]
    newline = "\r\n" if header.endswith("\r\n") else "\n"
    replacement = newline.join(
        prefix + line if line else "" for line in fragment.splitlines()
    )
    if original_lines[replacement_end - 1].endswith(("\n", "\r")):
        replacement += newline
    candidate = (
        "".join(original_lines[: section.header_start])
        + replacement
        + "".join(original_lines[replacement_end:])
    )

    # Check structure before parsing: parsers may collapse duplicate sections
    # or accept leftover markers as attribute names.
    _, result_sections, result_markers = _scan_docstring(candidate)
    if sum(s.title == "Attributes" for s in result_sections) != 1:
        raise fail("generated docstring must contain exactly one Attributes section")
    if result_markers:
        raise fail("generated docstring still contains an @attrs marker")
    try:
        # Normalize line endings for the parser only; the stored string keeps
        # its original layout.
        normalized = candidate.replace("\r\n", "\n").replace("\r", "\n")
        if section.style == "numpy":
            # Register custom headings so their text cannot be misread as
            # additional attributes by the default parser.
            parser = NumpydocParser()
            for other in result_sections:
                if other.style == "numpy" and other.title not in parser.sections:
                    parser.add_section(_LiteralNumpySection(other.title, "custom"))
            parsed = parser.parse(normalized)
        else:
            parsed = parse(normalized, style=parser_style)
    except ParseError as exc:
        raise fail(f"invalid generated {section.style} docstring: {exc}") from exc
    # Compare descriptions by content, ignoring wrapping and indentation
    # introduced by composition and parsing. Keep field order significant.
    actual = [
        (item.arg_name, " ".join((item.description or "").split()))
        for item in parsed.params
        if item.args[0] == "attribute"
    ]
    expected = [
        (name, " ".join((description or "").split()))
        for name, description in fields.items()
    ]
    if actual != expected:
        raise fail("generated Attributes do not match model fields")
    return candidate
