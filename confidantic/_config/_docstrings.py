"""Replace marked attribute sections without rewriting surrounding text."""

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


class _TextSection(Section):
    @property
    def title_pattern(self) -> str:
        return rf"^({re.escape(self.title)})[ \t]*\n{'-' * len(self.title)}[ \t]*$"


_Style = Literal["numpy", "google"]
_STYLES = {"numpy": DocstringStyle.NUMPYDOC, "google": DocstringStyle.GOOGLE}


@dataclass(frozen=True)
class _Section:
    title: str
    style: _Style
    start: int
    body: int
    end: int


def _scan(text: str) -> tuple[list[str], list[_Section], list[int]]:
    # Keep line indices aligned with the original, unlike cleandoc(), which
    # removes leading/trailing empty lines. Expand tabs only in the scan view.
    lines = text.expandtabs().splitlines()
    margin = min(
        (len(line) - len(line.lstrip()) for line in lines[1:] if line.strip()),
        default=0,
    )
    lines = [line.lstrip() if i == 0 else line[margin:] for i, line in enumerate(lines)]
    headings: list[tuple[str, _Style, int, int]] = []
    markers: list[int] = []
    literal_indent: int | None = None
    fenced = False
    doctest = False
    for i, line in enumerate(lines):
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
                i + 1 < len(lines)
                and len(lines[i + 1].rstrip()) >= 3
                and set(lines[i + 1].rstrip()) == {"-"}
            ):
                headings.append((stripped, "numpy", i, i + 2))
            elif stripped.endswith(":") and stripped not in {"@attrs:"}:
                headings.append((stripped[:-1], "google", i, i + 1))
        if stripped in {"@attrs", "@attrs:"}:
            markers.append(i)

    sections: list[_Section] = []
    for j, (title, style, start, body) in enumerate(headings):
        end = next(
            (h[2] for h in headings[j + 1 :] if style == "google" or h[1] == "numpy"),
            len(lines),
        )
        if style == "google":
            end = next(
                (k for k in range(body, end) if lines[k] and not lines[k][0].isspace()),
                end,
            )
        sections.append(_Section(title, style, start, body, end))

    active: list[int] = []
    for i in markers:
        section = next((s for s in sections if s.body <= i < s.end), None)
        if section is not None:
            if section.title.lower() in {"example", "examples"}:
                continue
            entry_indent = min(
                (
                    len(line) - len(line.lstrip())
                    for line in lines[section.body : section.end]
                    if line.strip()
                ),
                default=0,
            )
            if len(lines[i]) - len(lines[i].lstrip()) > entry_indent:
                continue
        active.append(i)
    return lines, sections, active


def _description(text: str | None) -> str:
    return " ".join((text or "").split())


def replace_attributes(
    text: str,
    *,
    fields: dict[str, str | None],
    style: _Style | None,
    class_name: str,
) -> str:
    lines, sections, markers = _scan(text)
    if not markers:
        return text

    def fail(reason: str) -> ValueError:
        return ValueError(f"{class_name}: {reason}")

    attributes = [section for section in sections if section.title == "Attributes"]
    if len(attributes) != 1:
        raise fail("expected exactly one Attributes section")
    section = attributes[0]
    if len(markers) != 1 or not section.body <= markers[0] < section.end:
        raise fail("expected one @attrs marker inside Attributes")
    marker = lines[markers[0]]
    if section.style == "numpy" and (
        marker.rstrip() != "@attrs" or lines[section.start + 1].rstrip() != "----------"
    ):
        raise fail("invalid NumPy @attrs marker")
    if style is not None and style != section.style:
        raise fail(f"Attributes section does not match docstring_style={style!r}")
    selected = _STYLES[section.style]
    generated = Docstring(style=selected)
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
    fragment = compose(generated, style=selected, indent="    ").strip("\n")
    # Composers omit empty sections; retain the header and let validation
    # determine whether the parser accepts an empty Attributes section.
    if not fragment:
        fragment = (
            "Attributes\n----------" if section.style == "numpy" else "Attributes:"
        )
    raw = text.splitlines(keepends=True)
    end = section.end
    while end > section.body and not lines[end - 1].strip():
        end -= 1
    header = raw[section.start]
    prefix = header[: len(header) - len(header.lstrip(" \t"))]
    newline = "\r\n" if header.endswith("\r\n") else "\n"
    replacement = newline.join(
        prefix + line if line else "" for line in fragment.splitlines()
    )
    if raw[end - 1].endswith(("\n", "\r")):
        replacement += newline
    candidate = "".join(raw[: section.start]) + replacement + "".join(raw[end:])
    _, result_sections, result_markers = _scan(candidate)
    if sum(s.title == "Attributes" for s in result_sections) != 1:
        raise fail("generated docstring must contain exactly one Attributes section")
    if result_markers:
        raise fail("generated docstring still contains an @attrs marker")
    try:
        # Normalize line endings for the parser only; the stored string keeps
        # its original layout. Register opaque NumPy sections so their text
        # cannot be misread as additional attributes by the default parser.
        normalized = candidate.replace("\r\n", "\n").replace("\r", "\n")
        if section.style == "numpy":
            parser = NumpydocParser()
            for other in result_sections:
                if other.style == "numpy" and other.title not in parser.sections:
                    parser.add_section(_TextSection(other.title, "custom"))
            parsed = parser.parse(normalized)
        else:
            parsed = parse(normalized, style=selected)
    except ParseError as exc:
        raise fail(f"invalid generated {section.style} docstring: {exc}") from exc
    actual = [
        (item.arg_name, _description(item.description))
        for item in parsed.params
        if item.args[0] == "attribute"
    ]
    expected = [
        (name, _description(description)) for name, description in fields.items()
    ]
    if actual != expected:
        raise fail("generated Attributes do not match model fields")
    return candidate
