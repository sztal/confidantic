"""Context-local configuration state."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar, Self

from confidantic._config.base import BaseConfig

__all__ = ("BaseContext",)


class BaseContext(BaseConfig):
    """Expose one active configuration per execution context.

    Instances retain :class:`BaseConfig` construction and validation semantics.
    Constructing an instance does not activate it; use :meth:`set` for a
    persistent activation or :meth:`temporary` for a scoped activation.

    The active instance is local to the current thread and asynchronous task.
    Each subclass receives an independent context variable automatically.
    """

    _current: ClassVar[ContextVar[Self]] = ContextVar("BaseContext.current")

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        cls._current = ContextVar(f"{cls.__module__}.{cls.__qualname__}.current")

    @classmethod
    def current(cls) -> Self:
        """Return the active instance for the current execution context.

        If no instance has been activated, one is constructed through the
        normal :class:`BaseConfig` settings sources and retained for subsequent
        calls in the same execution context.

        Returns
        -------
        Self
            Active instance of the receiving context class.
        """
        try:
            return cls._current.get()
        except LookupError:
            context = cls()
            cls._current.set(context)
            return context

    @classmethod
    def set(cls, context: Self) -> Self:
        """Set the active instance for the current execution context.

        Parameters
        ----------
        context
            Validated instance to activate.

        Returns
        -------
        Self
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
    def temporary(cls, context: Self) -> Iterator[Self]:
        """Temporarily activate an instance in the current execution context.

        Parameters
        ----------
        context
            Validated instance to activate for the duration of the context
            manager.

        Yields
        ------
        Self
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
