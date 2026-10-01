"""Pydantic annotations for paths, flexible inputs, and executable directives."""

import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import (
    Annotated,
    Any,
    TypeAlias,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import ImportString, PlainSerializer
from pydantic.functional_validators import (
    AfterValidator,
    WrapValidator,
)
from pydantic_settings import NoDecode
from typing_extensions import TypeVar as TypeVarWithDefault

from confidantic.utils import _call_mapping, get_import_string, import_from_string, make

__all__ = (
    "AbsolutePath",
    "Call",
    "CommaDelimited",
    "Delimited",
    "Import",
    "Make",
    "Map",
    "NoDecode",
    "SemiColonDelimited",
    "TabDelimited",
    "WhitespaceDelimited",
    "get_proper_args",
)

T = TypeVar("T")
P = TypeVarWithDefault("P", bound=Path, default=Path)


def get_proper_args(annotation: Any) -> Iterator[type]:
    """Recursively yield type-valued leaves from annotation arguments.

    Union members and generic arguments are traversed in order; generic origins
    are not yielded. ``Annotated`` metadata is traversed too, so metadata that
    is itself a type is included. Non-type leaves are ignored. This is not a
    normalization of the annotation into its accepted runtime types.

    Parameters
    ----------
    annotation
        The annotation to iterate over.

    Yields
    ------
    type
        The next type-valued leaf, without deduplication.

    Examples
    --------
    >>> list(get_proper_args(list[int | str]))
    [<class 'int'>, <class 'str'>]
    >>> list(get_proper_args(Annotated[int, str]))
    [<class 'int'>, <class 'str'>]
    """
    origin = get_origin(annotation)
    if not origin:
        if isinstance(annotation, type):
            yield annotation
        return
    for arg in get_args(annotation):
        yield from get_proper_args(arg)


# -----------------------------------------------------------------------------------
# AbsolutePath
# ----------------------------------------------------------------------------------


def _resolve_absolute_path(value: Path) -> Path:
    return value.resolve()


#: A Pydantic annotation for resolved absolute paths.
#: Used without a type parameter, validates values as :class:`pathlib.Path`.
#: A path annotation can be provided to retain its validation, for example
#: ``AbsolutePath[FilePath]`` or ``AbsolutePath[DirectoryPath]``.
#: Resolution follows symlinks and uses the current working directory for relative
#: inputs; it does not expand ``~``. Existence is required only by a supplied
#: constraint such as ``FilePath``, which runs before resolution.
AbsolutePath: TypeAlias = Annotated[P, AfterValidator(_resolve_absolute_path)]


# ------------------------------------------------------------------------------------
# Delimited string sequences
# -----------------------------------------------------------------------------------


def Delimited(sep: str | None = None) -> Any:
    """Return an annotation for delimiter-separated sequence inputs.

    Normal validation is attempted first, including item coercion. If it
    fails for a string, JSON decoding and validation are attempted next, then
    delimiter splitting with whitespace stripped from every item. If all
    attempts fail, the original validation error is raised. Settings-source
    JSON decoding is disabled by ``NoDecode`` so this fallback handles strings.
    CLI sources may parse list syntax before this validator receives the value.
    Splitting has no quoting or escape syntax; use JSON for embedded separators.

    Parameters
    ----------
    sep
        Separator passed to :meth:`str.split`. The default ``None`` splits on
        runs of whitespace; explicit separators retain empty items.

    Returns
    -------
    Any
        A generic annotation to parameterize with the desired validated type,
        for example ``Delimited("|")[list[int]]``.

    Examples
    --------
    >>> from pydantic import TypeAdapter
    >>> adapter = TypeAdapter(Delimited("|")[list[int]])
    >>> adapter.validate_python("1 | 2")
    [1, 2]
    >>> adapter.validate_python("[3, 4]")
    [3, 4]
    >>> adapter.validate_python(["5"])
    [5]
    """

    def _validate_delimited(value: Any, handler: Callable[[Any], Any]) -> Any:
        try:
            return handler(value)
        except Exception as e1:
            try:
                if isinstance(value, str):
                    try:
                        return handler(json.loads(value))
                    except Exception:
                        pass
                    values = [v.strip() for v in value.split(sep)]
                    return handler(values)
                raise e1
            except Exception as e2:
                raise e1 from e2

    return Annotated[Annotated[T, NoDecode], WrapValidator(_validate_delimited)]


#: Delimited input using commas; parameterize with a collection type.
CommaDelimited = Delimited(",")
#: Delimited input using semicolons.
SemiColonDelimited = Delimited(";")
#: Delimited input using runs of whitespace.
WhitespaceDelimited = Delimited()
#: Delimited input using tabs.
TabDelimited = Delimited("\t")


# -----------------------------------------------------------------------------------
# Dict-like string mappings
# -----------------------------------------------------------------------------------


def _dict_like(value: Any, handler: Callable[[Any], Any]) -> Any:
    try:
        return handler(value)
    except Exception as e1:
        try:
            if isinstance(value, str):
                try:
                    return handler(json.loads(value))
                except Exception:
                    pass
                pairs = [
                    item.strip().split("=", maxsplit=1)
                    for item in re.split(
                        r",\s*|\s+(?=[^,\s=]+\s*=)",
                        value.strip().rstrip(",").rstrip(),
                    )
                ]
                if any(len(pair) != 2 or not pair[0] for pair in pairs):
                    raise ValueError(
                        "Map values must contain key=value pairs separated by commas or whitespace"
                    )
                return handler({key.strip(): item.strip() for key, item in pairs})
            raise e1
        except Exception as e2:
            raise e1 from e2


#: Validate normally first, then try JSON and ``key=value`` parsing for strings.
#: Pairs may be separated by commas or whitespace before the next key; surrounding
#: whitespace and trailing commas are stripped. Repeated keys keep the last value.
#: Only the first ``=`` in each pair separates the key and value. This syntax has
#: no quoting or escaping; use JSON for values containing pair separators.
#: Parameterize with a mapping type, such as ``Map[dict[str, int]]``. Settings-source
#: JSON decoding is disabled, and failed fallbacks re-raise the original error.
Map: TypeAlias = Annotated[T, NoDecode, WrapValidator(_dict_like)]


# -----------------------------------------------------------------------------------
# Import directive annotation
# -----------------------------------------------------------------------------------


#: A Pydantic annotation for importable objects. Import strings are resolved using
#: :class:`pydantic.ImportString`; serialization uses :func:`get_import_string`.
#: Importability is not checked during serialization; instances serialize as their
#: type unless they expose their own module and qualified name.
Import: TypeAlias = Annotated[
    ImportString[T],
    PlainSerializer(get_import_string, return_type=str),
]


# -----------------------------------------------------------------------------------
# Call directive annotation
# -----------------------------------------------------------------------------------


def _call(value: Any, handler: Callable[[Any], Any]) -> Any:
    if isinstance(value, Mapping):
        return handler(_call_mapping(value) if "@call" in value else value)
    if isinstance(value, str):
        return handler(import_from_string(value, Callable)())
    return handler(value() if callable(value) else value)


#: A Pydantic annotation that evaluates a callable during validation. Callables and
#: import strings are called without arguments. A mapping with ``@call`` supplies
#: the callable or its import string, optional ``@args``, and keyword arguments in
#: its remaining entries. Nested arguments are not evaluated. Other values pass
#: through to normal validation; strings are always treated as import strings.
#: The called result is validated as T; the directive is not retained for dumping.
Call: TypeAlias = Annotated[T, WrapValidator(_call)]


# -----------------------------------------------------------------------------------
# Make directive annotation
# -----------------------------------------------------------------------------------


def _make(value: Any, handler: Callable[[Any], Any]) -> Any:
    return make(value, handler)


#: Evaluate directives with :func:`confidantic.utils.make` before validation.
#: Mapping values, lists, and tuples are traversed recursively. Nested strings
#: and callables remain data; top-level strings and callables are called without
#: arguments. Mapping keys and values returned by calls are not traversed.
#: The built value is validated as T; dumping uses that value's serialization,
#: without automatically recovering its original directive.
Make: TypeAlias = Annotated[T, WrapValidator(_make)]
