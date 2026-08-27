"""Context-local configuration state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar, TypeVar, cast

from confidantic.config.base import BaseConfig

__all__ = ("BaseContext",)

_ContextT = TypeVar("_ContextT", bound="BaseContext")


class BaseContext(BaseConfig):
    """Expose one active configuration per execution context.

    Instances retain :class:`BaseConfig` construction and validation semantics.
    Constructing an instance does not activate it; use :meth:`set` for a
    persistent activation or :meth:`temporary` for a scoped activation.

    The active instance is local to the current thread and asynchronous task.
    Each subclass receives an independent context variable automatically.
    """

    _current: ClassVar[ContextVar[BaseContext]] = ContextVar("BaseContext.current")

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        cls._current = ContextVar(f"{cls.__module__}.{cls.__qualname__}.current")

    @classmethod
    def current(cls: type[_ContextT]) -> _ContextT:
        """Return the active instance for the current execution context.

        If no instance has been activated, one is constructed through the
        normal :class:`BaseConfig` settings sources and retained for subsequent
        calls in the same execution context.

        Returns
        -------
        _ContextT
            Active instance of the receiving context class.
        """
        try:
            return cast(_ContextT, cls._current.get())
        except LookupError:
            context = cls()
            cls._current.set(context)
            return context

    @classmethod
    def set(cls: type[_ContextT], context: _ContextT) -> _ContextT:
        """Set the active instance for the current execution context.

        Parameters
        ----------
        context
            Validated instance to activate.

        Returns
        -------
        _ContextT
            The activated instance.

        Raises
        ------
        TypeError
            If ``context`` is not an instance of the receiving class.
        """
        if not isinstance(context, cls):
            raise TypeError(
                f"Expected an instance of {cls.__name__}, got {type(context).__name__}"
            )
        cls._current.set(context)
        return context

    @classmethod
    @contextmanager
    def temporary(cls: type[_ContextT], context: _ContextT) -> Iterator[_ContextT]:
        """Temporarily activate an instance in the current execution context.

        Parameters
        ----------
        context
            Validated instance to activate for the duration of the context
            manager.

        Yields
        ------
        _ContextT
            The temporarily activated instance.

        Raises
        ------
        TypeError
            If ``context`` is not an instance of the receiving class.
        """
        if not isinstance(context, cls):
            raise TypeError(
                f"Expected an instance of {cls.__name__}, got {type(context).__name__}"
            )
        token = cls._current.set(context)
        try:
            yield context
        finally:
            cls._current.reset(token)
