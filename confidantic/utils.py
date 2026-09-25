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
        ``True`` if ``ipykernel`` is loaded or the active IPython shell's class
        name is ``ZMQInteractiveShell``; ``False`` otherwise.

    Notes
    -----
    The standard IPython terminal shell is not recognized as a kernel unless
    ``ipykernel`` has also been imported. Detection is a heuristic, not a check
    that a kernel is running.
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
    """Describe an object or its type using module and qualified names.

    Parameters
    ----------
    obj
        The object to get the import string for.

    Returns
    -------
    str
        The module name for a module, otherwise ``module:qualname``. Objects
        without those attributes fall back to their type's identifier.

    Notes
    -----
    The identifier is not checked for importability. Local classes, lambdas,
    and unregistered dynamically generated classes may not be importable.
    An ordinary instance identifies its class, not its state.

    Examples
    --------
    >>> get_import_string(dict)
    'builtins:dict'
    >>> get_import_string({"answer": 42})
    'builtins:dict'
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
        Module or object path accepted by Pydantic ``ImportString``, such as
        ``"collections"``, ``"builtins:dict"``, or ``"builtins.dict"``.
    type_hint
        Type or type annotation the imported object must satisfy.

    Returns
    -------
    Any
        The imported object after validation against ``type_hint``.

    Raises
    ------
    ValidationError
        If the import cannot be resolved or its value fails validation.
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
    """Evaluate call directives and optionally validate the result.

    Mapping values, lists, and tuples are traversed recursively. A mapping
    containing ``@call`` invokes that callable or import string with optional
    iterable ``@args`` and all remaining entries as keyword arguments. Other
    mappings become plain dictionaries. Mapping keys are left unchanged.

    A top-level string is imported and called without arguments; a top-level
    callable is also called without arguments. Nested strings and callables
    remain unchanged unless used as an ``@call`` target. Return values from
    calls are not traversed again. Other container types are not traversed.

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
        optional handler once, after evaluation.

    Examples
    --------
    >>> make("builtins:list")
    []
    >>> make({"label": "builtins:list", "value": {"@call": "builtins:list"}})
    {'label': 'builtins:list', 'value': []}
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
