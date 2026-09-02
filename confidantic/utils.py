import sys
from collections.abc import Callable, Iterable, Mapping
from functools import singledispatch
from types import ModuleType
from typing import Any, cast

from pydantic import ImportString, TypeAdapter

__all__ = (
    "get_import_string",
    "import_from_string",
    "is_runtime_jupyterlike",
    "make",
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
    type_hint
        Type or type annotation the imported object must satisfy.

    Returns
    -------
    Any
        The imported object.
    """
    import_type = cast(Any, ImportString)[type_hint]
    return TypeAdapter(import_type).validate_python(import_string)


def _call_mapping(value: Mapping[Any, Any]) -> Any:
    if "@call" not in value:
        errmsg = "Call mappings require an '@call' key"
        raise ValueError(errmsg)
    target = value["@call"]
    args = value.get("@args", ())
    if not isinstance(args, Iterable):
        raise ValueError("'@args' must be an iterable")
    kwargs = {key: item for key, item in value.items() if key not in {"@args", "@call"}}
    callable_value = (
        import_from_string(target, Callable) if isinstance(target, str) else target
    )
    return callable_value(*args, **kwargs)


def make(value: Any, handler: Callable[[Any], Any] | None = None) -> Any:
    """Evaluate nested Make directives in a value.

    Parameters
    ----------
    value
        Value containing call mappings, import strings, or callable values.
    handler
        Optional final validator used by :class:`confidantic.annotations.Make`.
        Direct callers can omit it to receive the evaluated value directly.

    Returns
    -------
    Any
        The value after recursively evaluating call mappings and applying the
        optional handler.
    """

    def build(item: Any) -> Any:
        if isinstance(item, Mapping):
            built = {key: build(nested_value) for key, nested_value in item.items()}
            return _call_mapping(built) if "@call" in built else built
        if isinstance(item, list):
            return [build(nested_value) for nested_value in item]
        if isinstance(item, tuple):
            return tuple(build(nested_value) for nested_value in item)
        return item

    if isinstance(value, Mapping | list | tuple):
        result = build(value)
    elif isinstance(value, str):
        result = import_from_string(value, Callable)()
    elif callable(value):
        result = value()
    else:
        result = value
    return handler(result) if handler is not None else result
