"""Rich presentation loaded only when configuration information is requested."""

from io import StringIO
from typing import Any, Literal, get_origin

from pydantic import BaseModel
from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.pretty import Pretty
from rich.style import Style
from rich.table import Table
from rich.text import Text


class _InfoRenderer:
    """Build and render tables for one model with shared presentation options.

    The model supplies ordered field metadata. An optional instance supplies
    stored Python values; rendering neither serializes them nor runs factories.

    Parameters
    ----------
    model
        Model class supplying declared fields; extras and computed fields are omitted.
    header
        Whether to show the model class name as the table title.
    describe
        Whether to add a field-description column.
    colors
        Whether to style cells and request terminal output when rendering. Rich
        still applies its environment controls to the final output.
    respect_field_repr
        Whether to omit fields configured with ``repr=False``.
    """

    def __init__(
        self,
        model: type[BaseModel],
        *,
        header: bool,
        describe: bool,
        colors: bool,
        respect_field_repr: bool,
    ) -> None:
        self._model = model
        self._header = header
        self._describe = describe
        self._colors = colors
        self._respect_field_repr = respect_field_repr

    def build_table(
        self,
        *,
        instance: BaseModel | None = None,
        types: bool,
        defaults: bool,
    ) -> Table:
        """Build a table from model metadata and optional current values.

        Parameters
        ----------
        instance
            Model instance supplying stored values, or None to omit the value
            column. Values are displayed with their Python representations.
        types
            Whether to display field annotations.
        defaults
            Whether to display static defaults, required markers, and default
            factory names. Default factories are never called.

        Returns
        -------
        Table
            Unrendered table in model field order. No console output is produced.
        """
        colors = self._colors
        null_style = None if colors else Style()
        highlighter = None if colors else NullHighlighter()
        table = Table(
            title=self._model.__name__ if self._header else None,
            header_style="table.header" if colors else null_style,
            border_style=null_style,
            title_style=null_style,
        )
        table.add_column("Option", style="cyan" if colors else None, no_wrap=True)
        if types:
            table.add_column("Type", style="magenta" if colors else None)
        if instance is not None:
            table.add_column("Value")
        if defaults:
            table.add_column("Default")
        if self._describe:
            table.add_column("Description")

        for field_name, field in self._model.model_fields.items():
            if self._respect_field_repr and not field.repr:
                continue
            cells: list[Any] = [Text(field_name)]
            if types:
                annotation = field.annotation
                if annotation is type(None):
                    annotation_name = "None"
                elif get_origin(annotation) is None and isinstance(annotation, type):
                    annotation_name = annotation.__name__
                else:
                    annotation_name = str(annotation).removeprefix("typing.")
                cells.append(Text(annotation_name))
            if instance is not None:
                cells.append(
                    Pretty(getattr(instance, field_name), highlighter=highlighter)
                )
            if defaults:
                default: Text | Pretty
                if field.is_required():
                    default = Text("required", style="bold red" if colors else "")
                elif field.default_factory is not None:
                    factory_name = getattr(
                        field.default_factory,
                        "__name__",
                        type(field.default_factory).__name__,
                    )
                    default = Text(
                        f"<factory: {factory_name}>",
                        style="dim" if colors else "",
                    )
                else:
                    default = Pretty(
                        field.get_default(call_default_factory=False),
                        highlighter=highlighter,
                    )
                cells.append(default)
            if self._describe:
                cells.append(Text(field.description or ""))
            table.add_row(*cells)
        return table

    def render(
        self,
        table: Table,
        *,
        output: Literal["table", "string", "print"],
    ) -> Table | str | None:
        """Return a table or render it to a string or the default console.

        Parameters
        ----------
        table
            Prepared Rich table; returned unchanged in table mode.
        output
            ``"table"`` returns the object, ``"string"`` captures console output,
            and ``"print"`` writes to the default console and returns None.

        Raises
        ------
        ValueError
            If the output mode is unsupported.
        """
        if output not in {"table", "string", "print"}:
            raise ValueError(f"Invalid output mode: {output!r}")
        if output == "table":
            return table

        buffer = StringIO() if output == "string" else None
        Console(
            file=buffer,
            color_system="auto" if self._colors else None,
            force_terminal=self._colors,
        ).print(table)
        return buffer.getvalue() if buffer is not None else None
