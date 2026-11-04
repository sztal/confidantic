"""Optional composition and parsing for generated Attributes sections.

The layout scanner loads this module only for a validated insertion request.
Parser-specific objects stay here; callers exchange text and field descriptions.
"""

import re
from collections.abc import Iterable, Mapping
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


class _LiteralNumpySection(Section):
    """Treat a custom NumPy section as text rather than additional attributes."""

    @property
    def title_pattern(self) -> str:
        # Custom titles may contain regex syntax, such as parentheses.
        return rf"^({re.escape(self.title)})[ \t]*\n{'-' * len(self.title)}[ \t]*$"


class _AttributeDocstringBackend:
    """Compose and parse one docstring style with class-qualified diagnostics.

    Composition preserves field order and descriptions. Parsing returns field
    names and whitespace-normalized descriptions for independent comparison by
    the caller, validating the complete document rather than just its new section.
    """

    def __init__(self, style: Literal["numpy", "google"], *, class_name: str) -> None:
        self._style = style
        self._class_name = class_name
        self._parser_style = (
            DocstringStyle.NUMPYDOC if style == "numpy" else DocstringStyle.GOOGLE
        )

    def compose(self, fields: Mapping[str, str | None]) -> str:
        """Compose an Attributes section, retaining its heading when empty."""
        generated = Docstring(style=self._parser_style)
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
        fragment = compose(generated, style=self._parser_style, indent="    ").strip(
            "\n"
        )
        # Composers omit empty sections; parsing decides whether they are valid.
        return fragment or (
            "Attributes\n----------" if self._style == "numpy" else "Attributes:"
        )

    def attributes(
        self, text: str, *, custom_numpy_titles: Iterable[str]
    ) -> list[tuple[str, str]]:
        """Parse a complete docstring and return its normalized attribute entries."""
        try:
            # Normalize only the parser's view, leaving the stored string intact.
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            if self._style == "numpy":
                parser = NumpydocParser()
                for title in custom_numpy_titles:
                    if title not in parser.sections:
                        parser.add_section(_LiteralNumpySection(title, "custom"))
                parsed = parser.parse(normalized)
            else:
                parsed = parse(normalized, style=self._parser_style)
        except ParseError as error:
            raise ValueError(
                f"{self._class_name}: invalid generated {self._style} docstring: {error}"
            ) from error
        return [
            (item.arg_name, " ".join((item.description or "").split()))
            for item in parsed.params
            if item.args[0] == "attribute"
        ]
