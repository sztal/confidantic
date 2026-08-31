# %% Define a context-local configuration -------------------------------------------

"""Use :class:`BaseContext` to retain one active configuration per context.

The active configuration is local to the current thread and asynchronous task.
Use :meth:`BaseContext.set` for a persistent replacement or
:meth:`BaseContext.temporary` for a scoped override.
"""

from confidantic import ConfigModelDict
from confidantic.context import BaseContext


class RequestContext(BaseContext):
    """Configuration available to work handling a request."""

    model_config = ConfigModelDict(env_prefix="CONTEXT_EXAMPLE_")

    request_id: str = "default"
    debug: bool = False


# %% Resolve and replace the active context ------------------------------------------

# `current()` lazily creates and retains an instance when none has been activated.
default_context = RequestContext.current()
assert default_context.request_id == "default"
assert RequestContext.current() is default_context

active_context = RequestContext.set(RequestContext(request_id="request-42"))
assert RequestContext.current() is active_context

# %% Temporarily override the active context -----------------------------------------

with RequestContext.temporary(RequestContext(request_id="request-42", debug=True)):
    assert RequestContext.current().debug is True
    assert RequestContext.current().request_id == "request-42"

# The previous active context is restored, even if the `with` block raises.
assert RequestContext.current() is active_context
assert RequestContext.current().debug is False

# %% ---------------------------------------------------------------------------------
