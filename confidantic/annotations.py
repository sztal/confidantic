from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import (
    Annotated,
    Any,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import (
    Json,
    JsonValue,
    NegativeFloat,
    NegativeInt,
    NonNegativeFloat,
    NonNegativeInt,
    NonPositiveFloat,
    NonPositiveInt,
    PositiveFloat,
    PositiveInt,
)
from pydantic.functional_validators import (
    AfterValidator,
    BeforeValidator,
    WrapValidator,
)
from pydantic_settings import NoDecode

__all__ = (
    "AbsolutePath",
    "AfterValidator",
    "BeforeValidator",
    "CommaDelimited",
    "Delimited",
    "Json",
    "JsonValue",
    "NegativeFloat",
    "NegativeInt",
    "NoDecode",
    "NonNegativeFloat",
    "NonNegativeInt",
    "NonPositiveFloat",
    "NonPositiveInt",
    "PositiveFloat",
    "PositiveInt",
    "SemiColonDelimited",
    "WhitespaceDelimited",
    "get_proper_args",
)

T = TypeVar("T")
AbsolutePath = Annotated[Path, AfterValidator(Path.absolute)]


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
