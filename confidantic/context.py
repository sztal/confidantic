"""Context-local configuration state."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from typing import Self, TypeVar, cast
from weakref import WeakKeyDictionary

from confidantic._config.base import BaseConfig

__all__ = ("BaseContext",)


class BaseContext(BaseConfig):
    """Expose one active configuration per execution context.

    Instances retain :class:`BaseConfig` construction and validation semantics.
    Constructing an instance does not activate it; use :meth:`set` for a
    persistent activation or :meth:`temporary` for a scoped activation.

    The active instance is local to the current thread and asynchronous task.
    Each subclass receives independent process-local storage lazily. Serializing
    an instance does not transfer ambient activation into a fresh interpreter.
    """

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
            return _context_var(cls).get()
        except LookupError:
            context = cls()
            _context_var(cls).set(context)
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
        _context_var(cls).set(context)
        return context

    @classmethod
    @contextmanager
    def temporary(cls, context: Self) -> Generator[Self, None, None]:
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
        variable = _context_var(cls)
        token = variable.set(context)
        try:
            yield context
        finally:
            variable.reset(token)


_ContextT = TypeVar("_ContextT", bound=BaseContext)
_CONTEXT_VARS: WeakKeyDictionary[type[BaseContext], ContextVar[BaseContext]] = (
    WeakKeyDictionary()
)
_CONTEXT_VARS_LOCK = RLock()


def _context_var(cls: type[_ContextT]) -> ContextVar[_ContextT]:
    """Keep runtime state outside serializable classes without retaining them."""
    with _CONTEXT_VARS_LOCK:
        variable = _CONTEXT_VARS.get(cls)
        if variable is None:
            variable = ContextVar(f"{cls.__module__}.{cls.__qualname__}.current")
            _CONTEXT_VARS[cls] = variable
        return cast(ContextVar[_ContextT], variable)
