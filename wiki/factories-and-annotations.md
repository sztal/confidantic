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

`__recursive__` selects concrete defaults while generating fields. It does not
control resolution: `model_resolve()` always resolves nested factories. A type,
type hint, or predicate can select defaults for nested generation; a required
field without a source value remains required. The generated nested annotation
exposes that dependency's fields to validation and CLI parsing.

Use `Factory[T]` when a factory is nested in another configuration model.
Factory configuration uses the same `BaseConfig` source resolution as ordinary
settings models. See
[`examples/factory_template.py`](../examples/factory_template.py) and
[`examples/factory_dynamic_template.py`](../examples/factory_dynamic_template.py).

Both examples build from an application instance, retaining its database defaults
while allowing overrides such as `--application.database.host`. The dynamic
example first selects a dependency type with `--types.database`, constructs its
template, then generates the configuration for the remaining CLI options. Their
final `info()` call requires `confidantic[rich]`; generation, CLI parsing, and
resolution work without optional dependencies.

### Implementation ownership

| Module                                                                    | Responsibility                                                                                                                          |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| [`factory.py`](../confidantic/_config/factory.py)                         | Public `Factory` methods, generic target compatibility, Pydantic schema integration, and the named serialization callback.              |
| [`_factory_build.py`](../confidantic/_config/_factory_build.py)           | `_FactoryModelBuilder` inspects constructors, applies recursive selectors, preserves annotation metadata, and prepares copied defaults. |
| [`_factory_resolution.py`](../confidantic/_config/_factory_resolution.py) | `_FactoryResolver` traverses values; `_ResolvedModelTypes` rebuilds model annotations and resolves recursive type references.           |

A builder belongs to one `model_from()` operation; nested generation creates
separate builders. Generated classes retain field definitions and copied-default
templates, not builders. The shared `_CopiedDefault` wrapper lets those templates
participate in settings-source merging while each configuration gets its own
mutable values.

A resolver and its resolved-type map belong to one `model_resolve()` call. The
map reuses generated types within that call without changing original classes.
An active traversal path detects value cycles; `contains_factory` uses a separate
visited set for discovery. Repeated factory values are resolved separately,
rather than cached as constructed objects.

Schema callbacks remain attached to their Pydantic schema and do not retain
builders or resolvers. Schema construction stays in `factory.py` because
Pydantic invokes it while the root `Factory` class is still being created.

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
