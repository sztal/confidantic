"""Path-oriented configuration models."""

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field, GetCoreSchemaHandler, model_validator
from pydantic_core import CoreSchema, core_schema

from confidantic._config.base import BaseConfig, ConfigModelDict

__all__ = ("BasePaths", "ExtensiblePath")

if TYPE_CHECKING:
    from pathlib import Path as _ExtensiblePathBase

else:
    _ExtensiblePathBase = type(Path())


class ExtensiblePath(_ExtensiblePathBase):
    """Concrete path with callable ``joinpath`` shorthand.

    Calling an instance appends the supplied path segments and returns another
    ``ExtensiblePath``. All standard :class:`pathlib.Path` operations remain
    available.

    Examples
    --------
    >>> path = ExtensiblePath("data")
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
        """Join path segments and return a path of the same concrete type.

        Parameters
        ----------
        *pathsegments
            Segments passed to :meth:`pathlib.Path.joinpath`. An absolute
            segment replaces the preceding path on the current platform.

        Returns
        -------
        ExtensiblePath
            Joined path, without expansion or filesystem resolution.
        """
        return type(self)(self.joinpath(*pathsegments))


class BasePaths(BaseConfig):
    """Base configuration containing canonical filesystem paths.

    ``root`` defaults to the current directory. It is expanded and canonicalized
    first. Every other relative path is joined to that root before being
    canonicalized. A path beginning with ``@field/`` resolves relative to a
    previously defined path field or extra. Absolute paths bypass joining but
    are still canonicalized. Paths need not exist.

    Subclasses may declare additional :class:`pathlib.Path`-compatible fields.
    Their validated values are canonicalized to ``ExtensiblePath``. Undeclared
    path values are accepted as Pydantic extra fields by default. Declared fields
    are resolved in model field order, followed by extras in their input order.
    All declared fields must have a concrete ``Path`` subclass annotation;
    optional and union path annotations are not accepted. Field constraints such
    as ``FilePath`` run before canonicalization, so relative existence checks
    use the current working directory rather than ``root``.

    ``~`` is expanded and existing symlinks are followed. A bare ``@field``
    resolves to the anchor itself; unknown or forward anchors raise a validation
    error. Root is resolved independently and cannot reference an anchor.
    Only canonical paths are retained: changing ``root`` or an anchor with
    :meth:`copy` or :meth:`mutate` does not relocate existing absolute paths.
    Supply new relative definitions for paths that should move.

    Examples
    --------
    >>> paths = BasePaths(root=Path.cwd(), data="data")
    >>> paths.data == Path.cwd().joinpath("data").resolve(strict=False)
    True
    >>> moved = paths.copy(root=paths.root / "elsewhere")
    >>> moved.data == paths.data
    True
    >>> moved.copy(data="data").data == moved.root / "data"
    True
    """

    model_config = ConfigModelDict(extra="allow", validate_default=True)

    __pydantic_extra__: dict[str, ExtensiblePath] = Field(init=False)

    root: ExtensiblePath = ExtensiblePath(".")
    """Root directory used to resolve relative path definitions."""

    def __call__(self, *args: Any, **kwargs: Any) -> ExtensiblePath:
        """Join path segments to the configured root directory.

        Parameters
        ----------
        *args
            Segments passed to :meth:`pathlib.Path.joinpath`. An absolute
            segment replaces the root on the current platform.
        **kwargs
            Forwarded to :meth:`pathlib.Path.joinpath`, whose standard
            implementation accepts only positional path segments.

        Returns
        -------
        ExtensiblePath
            Joined path, without additional expansion or canonicalization.
        """
        return self.root.joinpath(*args, **kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        invalid_fields = [
            name
            for name, field in cls.model_fields.items()
            if not isinstance(field.annotation, type)
            or not issubclass(field.annotation, Path)
        ]
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise TypeError(
                f"{cls.__name__} fields must use Path-compatible annotations: {fields}"
            )

    @model_validator(mode="after")
    def _canonicalize_paths(self) -> Self:
        root = _canonicalize_path(self.root)
        object.__setattr__(self, "root", root)
        anchors = {"root": root}

        for name in type(self).model_fields:
            if name == "root":
                continue
            value = object.__getattribute__(self, name)
            path = _canonicalize_path(value, root, anchors)
            object.__setattr__(self, name, path)
            anchors[name] = path

        if self.__pydantic_extra__ is not None:
            for name, value in self.__pydantic_extra__.items():
                path = _canonicalize_path(value, root, anchors)
                self.__pydantic_extra__[name] = path
                anchors[name] = path

        return self


def _canonicalize_path(
    path: ExtensiblePath,
    root: ExtensiblePath | None = None,
    anchors: dict[str, ExtensiblePath] | None = None,
) -> ExtensiblePath:
    expanded = path.expanduser()
    if root is not None and not expanded.is_absolute():
        anchor, *segments = expanded.parts or (".",)
        if anchor.startswith("@"):
            anchor_name = anchor[1:]
            if anchors is None or anchor_name not in anchors:
                raise ValueError(f"Unknown or forward path anchor: {anchor}")
            expanded = anchors[anchor_name].joinpath(*segments)
        else:
            expanded = root.joinpath(expanded)
    return ExtensiblePath(expanded.resolve(strict=False))
