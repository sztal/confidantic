"""Path-oriented configuration models."""

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field, GetCoreSchemaHandler, model_validator
from pydantic_core import CoreSchema, core_schema

from confidantic._config.base import BaseConfig, SettingsConfigDict

__all__ = ("BasePaths", "DynamicPath")

if TYPE_CHECKING:
    from pathlib import Path as _DynamicPathBase

else:
    _DynamicPathBase = type(Path())


class DynamicPath(_DynamicPathBase):
    """Concrete path with callable ``joinpath`` shorthand.

    Calling an instance appends the supplied path segments and returns another
    ``DynamicPath``. All standard :class:`pathlib.Path` operations remain
    available.

    Examples
    --------
    >>> path = DynamicPath("data")
    >>> path("raw", "items.json") == Path("data/raw/items.json")
    True
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            handler.generate_schema(Path),
        )

    def __call__(self, *pathsegments: str | PathLike[str]) -> Self:
        """Join path segments and return a dynamic path.

        Parameters
        ----------
        *pathsegments
                Child path segments to append.

        Returns
        -------
        DynamicPath
                Joined path.
        """
        return type(self)(self.joinpath(*pathsegments))


class BasePaths(BaseConfig):
    """Base configuration containing canonical filesystem paths.

    ``root`` is required. It is expanded and canonicalized first. Every other
    relative path is joined to that root before being canonicalized. Absolute
    paths bypass joining but are still canonicalized. Paths need not exist.

    Subclasses may declare additional ``DynamicPath`` fields. Undeclared path
    values are accepted as Pydantic extra fields by default.

    Examples
    --------
    >>> paths = BasePaths(root=Path.cwd(), data="data")
    >>> paths.data == Path.cwd().joinpath("data").resolve(strict=False)
    True
    """

    model_config = SettingsConfigDict(extra="allow", validate_default=True)

    __pydantic_extra__: dict[str, DynamicPath] = Field(init=False)

    root: DynamicPath
    """Root directory used to resolve relative path definitions."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        invalid_fields = [
            name
            for name, field in cls.model_fields.items()
            if field.annotation is not DynamicPath
        ]
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise TypeError(
                f"{cls.__name__} fields must use DynamicPath annotations: {fields}"
            )

    @model_validator(mode="after")
    def _canonicalize_paths(self) -> Self:
        root = _canonicalize_path(self.root)
        object.__setattr__(self, "root", root)

        for name in type(self).model_fields:
            if name == "root":
                continue
            value = object.__getattribute__(self, name)
            object.__setattr__(self, name, _canonicalize_path(value, root))

        if self.__pydantic_extra__ is not None:
            for name, value in self.__pydantic_extra__.items():
                self.__pydantic_extra__[name] = _canonicalize_path(value, root)

        return self


def _canonicalize_path(
    path: DynamicPath,
    root: DynamicPath | None = None,
) -> DynamicPath:
    expanded = path.expanduser()
    if root is not None and not expanded.is_absolute():
        expanded = root.joinpath(expanded)
    return DynamicPath(expanded.resolve(strict=False))
