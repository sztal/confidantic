# Use settings within a request or task

Sometimes several functions need request settings, but passing them through every
call would be awkward. [BaseContext][confidantic.context.BaseContext] provides an
explicit activation scope. This recipe needs only core Confidantic.

```pycon
>>> from confidantic.context import BaseContext
>>> class RequestContext(BaseContext):
...     request_id: str = "default"
...     debug: bool = False
>>> def describe_request() -> str:
...     """Read settings for the active request."""
...     current = RequestContext.current()
...     return f"{current.request_id}: debug={current.debug}"
>>> print(describe_request())
default: debug=False
>>> request = RequestContext(request_id="request-42", debug=True)
>>> with RequestContext.temporary(request):
...     print(describe_request())
request-42: debug=True
>>> print(describe_request())
default: debug=False

```

Constructing `request` validates it but does not activate it. The `with` block
activates it temporarily and restores the previous value even if the block raises
an exception. `current()` lazily creates and retains a default when no activation
exists. Each concrete context class has independent activation storage.

Use `RequestContext.set(request)` for a persistent replacement within the current
execution context. Prefer `temporary()` when the desired lifetime has a clear exit.
Activation checks the instance's class and retains it by reference; it does not
revalidate all fields. A validated copy is useful for changing selected settings:

```pycon
>>> current = RequestContext.current()
>>> with RequestContext.temporary(current.copy(debug=True)):
...     print(describe_request())
default: debug=True

```

After the first example, this prints `default: debug=True` inside the block and
leaves the previous activation intact afterward.

!!! note "Task-local bindings can share objects"

    New asynchronous tasks inherit the current object reference. Replacing one
    task's activation does not replace another's; mutating their shared instance
    can affect both. Frozen fields do not make nested mutable values immutable.

Worker processes need explicit settings input and activation. Serializing a context
instance transfers its data, not the sender's ambient activation. Prefer ordinary
function arguments when they make ownership clearer.

Read [state and lifetimes](../concepts/state-and-lifetimes.md) for the wider ownership
model and the [wiki context discussion](https://github.com/sztal/confidantic/blob/master/wiki/concepts/contexts.md)
for implementation boundaries.
