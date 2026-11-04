# Activate context-local settings

[context.py](../../examples/context.py) needs core Confidantic. It defines a
RequestContext with a request identifier and a debug flag, then checks lazy,
persistent, and temporary activation.

```console
uv run python examples/context.py
```

The script completes silently when its assertions pass. This excerpt follows its
RequestContext definition:

```python
default_context = RequestContext.current()
assert default_context.request_id == "default"
assert RequestContext.current() is default_context

active_context = RequestContext.set(RequestContext(request_id="request-42"))
assert RequestContext.current() is active_context
```

Construction alone does not activate a configuration. `current()` constructs once
on a missing activation; `set()` returns and retains the explicitly supplied instance.

## Scope an override

The script's temporary override is:

```python
with RequestContext.temporary(RequestContext(request_id="request-42", debug=True)):
    assert RequestContext.current().debug is True
    assert RequestContext.current().request_id == "request-42"
```

After the block, assertions confirm that the earlier active instance is restored
and debug is False. Restoration also happens if the block raises. Use a copied
configuration when an override should retain other fields from the current value.

New asynchronous tasks inherit existing activation by reference. Replacing the
binding is local; mutating a shared instance can affect both tasks. Worker processes
need explicit input/activation rather than relying on a sender's ambient context.

See [context concepts](../concepts/contexts.md),
[context internals](../api/context.md), and [all guides](README.md).
