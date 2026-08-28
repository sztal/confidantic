import sys
from functools import singledispatch
from types import ModuleType
from typing import Any, cast

from pydantic import ImportString, TypeAdapter

__all__ = (
    "get_import_string",
    "import_from_string",
    "is_runtime_jupyterlike",
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
