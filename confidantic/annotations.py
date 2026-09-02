import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Generic,
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


# -----------------------------------------------------------------------------------
# AbsolutePath
# ----------------------------------------------------------------------------------


def _resolve_absolute_path(value: Path) -> Path:
    return value.resolve()


#: A Pydantic annotation for resolved absolute paths.
#: Used without a type parameter, validates values as :class:`pathlib.Path`.
#: A path annotation can be provided to retain its validation, for example
#: ``AbsolutePath[FilePath]`` or ``AbsolutePath[DirectoryPath]``.
AbsolutePath: TypeAlias = Annotated[P, AfterValidator(_resolve_absolute_path)]


# ------------------------------------------------------------------------------------
# Delimited string sequences
# -----------------------------------------------------------------------------------


def Delimited(sep: str | None = None) -> Any:
    """Return an annotation for delimiter-separated sequence inputs.

    The returned annotation accepts an existing sequence unchanged, while
    splitting string inputs on ``sep`` before normal validation.
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


CommaDelimited = Delimited(",")
SemiColonDelimited = Delimited(";")
WhitespaceDelimited = Delimited()
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


Map: TypeAlias = Annotated[T, NoDecode, WrapValidator(_dict_like)]


# -----------------------------------------------------------------------------------
# Import directive annotation
# -----------------------------------------------------------------------------------


#: A Pydantic annotation for importable objects. Import strings are resolved using
#: :class:`pydantic.ImportString` and objects serialize as stable import strings.
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


class Call(Generic[T]):
    """A Pydantic annotation that evaluates a callable during validation.

    Callables and import strings are evaluated before validation. A mapping whose
    ``@call`` value identifies a callable is evaluated with ``@args`` as positional
    arguments and its remaining entries as keyword arguments. Other inputs are
    validated unchanged against the annotated type.
    """

    @classmethod
    def __class_getitem__(cls, item_type: type[T]) -> Any:
        """Return a call annotation whose result is validated as ``item_type``."""
        return Annotated[item_type, WrapValidator(_call)]


# -----------------------------------------------------------------------------------
# Make directive annotation
# -----------------------------------------------------------------------------------


class Make(Generic[T]):
    """A Pydantic annotation that evaluates nested call mappings.

    The annotation behaves like :class:`Call` for a callable or import string.
    Mappings and sequences are otherwise traversed recursively; mappings with an
    ``@call`` key are invoked after their arguments and keyword values are built.
    """

    @classmethod
    def __class_getitem__(cls, item_type: type[T]) -> Any:
        """Return a make annotation whose result is validated as ``item_type``."""
        return Annotated[item_type, WrapValidator(_make)]


def _make(value: Any, handler: Callable[[Any], Any]) -> Any:
    return make(value, handler)
