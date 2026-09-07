# Factories and annotations

Confidantic adds reusable input annotations and constructor-derived settings
models without replacing Pydantic validation.

## Factories

`Factory.model_from()` creates a concrete configuration class from a target
class or instance. Annotated constructor parameters become validated fields;
call `model_resolve()` to create the target:

```python
from dataclasses import dataclass

from confidantic import Factory


@dataclass
class Client:
    host: str
    timeout: float = 5.0


ClientConfig = Factory.model_from(Client)
client = ClientConfig(host="localhost").model_resolve()
```

Resolution is always recursive. Apply any configuration updates before calling
`model_resolve()`, for example with `copy()` or validation; the resolution call
does not accept update values. For `BaseConfig` models, `name=` is the only
option and controls the generated resolved model class name.

Pass constructor arguments when defaults should come from a constructed target
instance. Use `__recursive__` to turn matching concrete defaults into nested
factory fields and `__name__` to choose the generated model name:

```python
ClientConfig = Factory.model_from(
    Client, "localhost", timeout=10.0, __name__="LocalClientConfig"
)
```

Use `Factory[T]` when a factory is nested in another configuration model.
Factory configuration uses the same `BaseConfig` source resolution as ordinary
settings models. See
[`examples/factory.py`](../examples/factory.py) and
[`examples/factory_gated.py`](../examples/factory_gated.py).

The implementation is in
[`confidantic/_config/factory.py`](../confidantic/_config/factory.py).

## Input annotations

The annotations in [`confidantic/annotations.py`](../confidantic/annotations.py)
adapt common configuration values while retaining Pydantic validation:

- `AbsolutePath` resolves path values to absolute paths.
- `Delimited`, `CommaDelimited`, `SemiColonDelimited`, `WhitespaceDelimited`,
  and `TabDelimited` accept delimiter-separated strings for sequence fields.
- `Map` accepts JSON or `key=value` mapping strings.
- `Import` validates importable objects and serializes them as import strings.
- `Call` and `Make` describe trusted callable and constructor directives.

```python
from pathlib import Path

from confidantic import BaseConfig
from confidantic.annotations import AbsolutePath, CommaDelimited


class PathsConfig(BaseConfig):
    root: AbsolutePath
    hosts: CommaDelimited[list[str]]


config = PathsConfig(root=Path("."), hosts="api,worker")
```

[`examples/delimited.py`](../examples/delimited.py) demonstrates delimited
values and mappings. [`examples/directive_annotations.py`](../examples/directive_annotations.py)
shows import, call, and make directives.
