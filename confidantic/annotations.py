from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import ImportString, PlainSerializer
from pydantic.functional_validators import (
    AfterValidator,
    WrapValidator,
)
from pydantic_core import core_schema
from pydantic_settings import NoDecode
from typing_extensions import TypeVar as TypeVarWithDefault

from confidantic.utils import get_import_string, import_from_string

__all__ = (
    "AbsolutePath",
    "Call",
    "CommaDelimited",
    "Delimited",
    "Import",
    "Make",
    "NoDecode",
    "SemiColonDelimited",
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


class AbsolutePath(Path, Generic[P]):
    """A Pydantic annotation for resolved absolute paths.

    Used without a type parameter, validates values as :class:`pathlib.Path`.
    A path annotation can be provided to retain its validation, for example
    ``AbsolutePath[FilePath]`` or ``AbsolutePath[DirectoryPath]``.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            _resolve_absolute_path,
            handler(Path),
        )

    def __class_getitem__(cls, path_type: type[P]) -> Any:
        """Return an absolute-path annotation retaining ``path_type`` validation."""
        return Annotated[path_type, AfterValidator(_resolve_absolute_path)]


# ------------------------------------------------------------------------------------
# Delimited string sequences
# -----------------------------------------------------------------------------------


def Delimited(sep: str | None = None) -> type[Sequence]:
    """Return an annotation for delimiter-separated sequence inputs.

    The returned annotation accepts an existing sequence unchanged, while
    splitting string inputs on ``sep`` before normal validation.
    """

    def _validate_delimited(value: Any, handler: Callable) -> Any:
        try:
            return handler(value)
        except Exception as e1:
            try:
                if isinstance(value, str):
                    values = [v.strip() for v in value.split(sep)]
                    return handler(values)
                raise e1
            except Exception as e2:
                raise e1 from e2

    return Annotated[Annotated[T, NoDecode], WrapValidator(_validate_delimited)]


CommaDelimited = Delimited(",")
SemiColonDelimited = Delimited(";")
WhitespaceDelimited = Delimited()


# -----------------------------------------------------------------------------------
# Import directive annotation
# -----------------------------------------------------------------------------------


class Import(Generic[T]):
    """A Pydantic annotation for importable objects.

    Values supplied as import strings are resolved using Pydantic's
    :class:`pydantic.ImportString` validation. Serialized values are always emitted as
    import strings, allowing models to be round-tripped through configuration files.
    """

    @classmethod
    def __class_getitem__(cls, item_type: type[T]) -> Any:
        """Return an import annotation constrained to ``item_type``."""
        return Annotated[
            ImportString[item_type],
            PlainSerializer(get_import_string, return_type=str),
        ]


# -----------------------------------------------------------------------------------
# Call directive annotation
# -----------------------------------------------------------------------------------


def _call(value: Any, handler: Callable) -> Any:
    if isinstance(value, Mapping):
        return handler(_call_mapping(value))
    if isinstance(value, str):
        return handler(import_from_string(value, Callable)())
    return handler(value())


def _call_mapping(value: Mapping[Any, Any]) -> Any:
    if "@call" not in value:
        errmsg = "Call mappings require an '@call' key"
        raise ValueError(errmsg)
    target = value["@call"]
    args = value.get("@args", ())
    kwargs = {key: item for key, item in value.items() if key not in {"@args", "@call"}}
    callable_value = (
        import_from_string(target, Callable) if isinstance(target, str) else target
    )
    return callable_value(*args, **kwargs)


class Call(Generic[T]):
    """A Pydantic annotation that evaluates a callable during validation.

    The annotation accepts a callable, an import string identifying a callable, or a
    mapping whose ``@call`` value identifies the callable. In mappings, ``@args``
    supplies positional arguments and all remaining entries supply keyword arguments.
    The result is then validated against the annotated type.
    """

    @classmethod
    def __class_getitem__(cls, item_type: type[T]) -> Any:
        """Return a call annotation whose result is validated as ``item_type``."""
        return Annotated[item_type, WrapValidator(_call)]


# -----------------------------------------------------------------------------------
# Make directive annotation
# -----------------------------------------------------------------------------------


def _make(value: Any, handler: Callable) -> Any:
    def build(item: Any) -> Any:
        if isinstance(item, Mapping):
            built = {key: build(value) for key, value in item.items()}
            return _call_mapping(built) if "@call" in built else built
        if isinstance(item, list):
            return [build(value) for value in item]
        if isinstance(item, tuple):
            return tuple(build(value) for value in item)
        return item

    if isinstance(value, Mapping):
        return handler(build(value))
    return _call(value, handler)


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
