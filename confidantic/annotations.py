from collections.abc import Callable, Sequence
from datetime import date, datetime, time
from io import TextIOBase
from pathlib import Path
from typing import (
    Annotated,
    Any,
    TypeVar,
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
from pydantic_extra_types import pendulum_dt
from pydantic_extra_types.country import CountryAlpha2
from pydantic_extra_types.currency_code import Currency
from pydantic_extra_types.language_code import LanguageAlpha2
from pydantic_extra_types.timezone_name import TimeZoneName
from pydantic_settings import NoDecode

from .utils import parse_date, parse_datetime, parse_time

__all__ = (
    "AbsolutePath",
    "AfterValidator",
    "BeforeValidator",
    "CommaDelimited",
    "Country",
    "Currency",
    "Date",
    "DateTime",
    "Delimited",
    "Duration",
    "Json",
    "JsonValue",
    "Language",
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
    "Time",
    "TimeZoneName",
    "WhitespaceDelimited",
)

T = TypeVar("T")
S = TypeVar("S", bound=str)
C = TypeVar("C", bound=Callable)

AbsolutePath = Annotated[Path, AfterValidator(Path.absolute)]
SerializationTarget = str | Path | TextIOBase
SerializationSource = str | bytes | bytearray | Path | TextIOBase

Country = CountryAlpha2
Language = LanguageAlpha2

Date = Annotated[pendulum_dt.Date | str | date, BeforeValidator(parse_date)]
Time = Annotated[pendulum_dt.Time | str | time, BeforeValidator(parse_time)]
DateTime = Annotated[
    pendulum_dt.DateTime | str | datetime, BeforeValidator(parse_datetime)
]
Duration = pendulum_dt.Duration


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
