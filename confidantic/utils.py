import sys
from functools import singledispatch
from types import ModuleType
from typing import Any, cast, get_args, get_origin

import pendulum as pdt
from pydantic import ImportString, TypeAdapter

__all__ = (
    "get_import_string",
    "get_proper_args",
    "import_from_string",
    "is_runtime_jupyterlike",
    "parse_date",
    "parse_datetime",
    "parse_time",
)


def is_runtime_jupyterlike() -> bool:
    """Determine whether code is running in a notebook-like kernel.

    Returns
    -------
    bool
        ``True`` for Jupyter-style kernel runtimes (including VS Code
        Interactive and notebooks), ``False`` otherwise.

    Notes
    -----
    This intentionally excludes the standard IPython terminal shell so
    CLI argument parsing remains available when running scripts via
    ``%run`` with command-line arguments.
    """
    if "ipykernel" in sys.modules:
        return True
    try:
        import IPython
    except Exception:
        return False
    get_ipython = getattr(IPython, "get_ipython", None)
    if get_ipython is None:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    return type(shell).__name__ == "ZMQInteractiveShell"


@singledispatch
def get_import_string(obj: Any) -> str:
    """Get the import string for an object.

    Parameters
    ----------
    obj
        The object to get the import string for.

    Returns
    -------
    str
        The import string for the object.
    """
    try:
        return f"{obj.__module__}:{obj.__qualname__}"
    except AttributeError:
        return get_import_string(type(obj))


@get_import_string.register
def _(obj: ModuleType) -> str:
    return obj.__name__


def import_from_string(import_string: str, type_hint: Any = Any) -> Any:
    """Import an object from an import string.

    Parameters
    ----------
    import_string
        The import string to import the object from.

    Returns
    -------
    Any
        The imported object.
    """
    import_type = cast(Any, ImportString)[type_hint]
    return TypeAdapter(import_type).validate_python(import_string)


def parse_date(d: Any) -> pdt.Date:
    """Parse a date from a string or return the date if already a Date."""
    if isinstance(d, pdt.Date):
        return d
    date_str = str(d)
    try:
        return pdt.Date.fromisoformat(date_str)
    except ValueError:
        return pdt.DateTime.fromisoformat(date_str).date()


def parse_datetime(dt: Any) -> pdt.DateTime:
    """Parse a datetime from a string or return the datetime if already a DateTime."""
    if isinstance(dt, pdt.DateTime):
        return dt
    dt_str = str(dt)
    return pdt.DateTime.fromisoformat(dt_str)


def parse_time(t: Any) -> pdt.Time:
    """Parse a time from a string or return the time if already a Time."""
    if isinstance(t, pdt.Time):
        return t
    t_str = str(t)
    try:
        return pdt.Time.fromisoformat(t_str)
    except ValueError:
        return pdt.DateTime.fromisoformat(t_str).time()


def get_proper_args(annotation: Any) -> type:
    """Iterate over the concrete types inside an annotation.

    For example, for a union annotation like ``int | str``, this yields
    ``int`` and ``str``. For an annotated annotation like
    ``Annotated[int, SomeValidator()]``, this yields ``int``.

    Parameters
    ----------
    annotation
        The annotation to iterate over.

    Yields
    ------
    type
        The next proper type in the annotation.
    """
    origin = get_origin(annotation)
    if not origin:
        if isinstance(annotation, type):
            yield annotation
        return
    for arg in get_args(annotation):
        yield from get_proper_args(arg)
