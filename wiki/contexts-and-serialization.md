# Contexts and serialization

## Context-local configuration

Subclass `BaseContext` when one configuration should be available throughout an
execution context. `current()` lazily creates the active value, `set()` makes a
replacement persistent, and `temporary()` restores the previous value when its
scope exits.

```python
from confidantic.context import BaseContext


class RequestContext(BaseContext):
    request_id: str = "default"


with RequestContext.temporary(RequestContext(request_id="request-42")):
    assert RequestContext.current().request_id == "request-42"
```

The context uses Python context-local state, so the active value is isolated per
thread or asynchronous task. See [`examples/context.py`](../examples/context.py)
for persistent and temporary replacements.

## Portable configuration documents

`BaseConfig.model_dump()` and `model_dump_json()` accept `context={"make": True}`
to add a `Make` directive for serialized `BaseConfig` values. The directive
records the concrete class import path, allowing `Make[Config]` to restore a
trusted document with its nested configuration types.

```python
from pydantic import BaseModel

from confidantic import BaseConfig
from confidantic.annotations import Make


class AppConfig(BaseConfig):
    retries: int = 3


class Document(BaseModel):
    config: Make[AppConfig]


config = AppConfig(retries=5)
data = config.model_dump(context={"make": True})
restored = Document.model_validate({"config": data}).config
assert restored.retries == 5
```

Make directives import and invoke the selected class, so only trusted documents
should be validated with this annotation. See
[`examples/serialization.py`](../examples/serialization.py) for nested configs
and ordinary Pydantic models.

## Optional formats and integrations

YAML and TOML serialization helpers are optional layers over the same model dump
and validation APIs. Install the corresponding package extra before using them;
[`examples/serialization.py`](../examples/serialization.py) covers both formats.

Other public integrations include [`Configurable`](../confidantic/configurable.py)
for configurable classes, [`paths.py`](../confidantic/paths.py) for path-aware
settings, [`logging.py`](../confidantic/logging.py) for logging configuration,
and [`types.py`](../confidantic/types.py) for shared types. Their runnable
examples are [`examples/configurable.py`](../examples/configurable.py) and
[`examples/logging_config.py`](../examples/logging_config.py).
