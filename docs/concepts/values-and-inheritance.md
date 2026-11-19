# Understand where values come from

A setting can receive a value from several places: Python code, a command line,
an environment variable, a file, or a declared default. Confidantic combines those
inputs before Pydantic validates them.

Two questions explain the result: **which configuration class supplied the value?**
and **which source within that class supplied it?**
The [Pydantic comparison](../getting-started/confidantic-vs-pydantic.md#inheritance-determines-source-priority)
explains how these rules add to upstream settings behavior.

## Sources within one class

The usual enabled sources run in this priority order: CLI, initializer, process
environment, dotenv, secret files, and directly declared defaults. Custom source
hooks can change the order within a class. Only the most-derived class parses CLI
arguments in an inheritance chain.

Higher priority determines which supplied value wins; it does not mean processing
stops early. Every configured source still runs. A malformed lower-priority input
can fail construction even if another source already supplied the field.

## Child classes before parents

A child class's sources and directly declared defaults come before the parent
class's sources and defaults. This lets a specialized configuration keep its own
policy. A child default can beat a parent environment variable:

```python
import os

from confidantic import BaseConfig, ConfigModelDict


class ParentConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="PARENT_")

    name: str = "parent"
    retries: int = 3


class ChildConfig(ParentConfig):
    model_config = ConfigModelDict(env_prefix="CHILD_")

    name: str = "child"


os.environ["PARENT_NAME"] = "from-environment"
os.environ["PARENT_RETRIES"] = "8"
print(ChildConfig().model_dump())
```

```text
{'name': 'child', 'retries': 8}
```

Run this as a standalone script without matching `CHILD_` variables. The child
provides its own name but leaves `retries` to the parent's sources. Merely declaring
a required child field without a default does not insert a default value that
blocks parent input.

For multiple inheritance, Python's method resolution order determines the sequence
of classes. You usually do not need that machinery for a single parent, but avoid
assuming that all environment values are considered before all defaults.

## Merge before validation

Mappings can contribute different keys across sources. Lists and other non-mapping
values replace lower-priority values. Existing nested model defaults can supply a
baseline for a partial update; see [nested settings](../guide/nested-settings.md).
These rules decide which input reaches Pydantic, whose types, constraints, and
validators then decide whether that input is acceptable.

`model_field_sources` helps explain top-level origins. It does not track every key
inside a merged dictionary. Read [the sources guide](../guide/sources.md) to use it,
or [the settings lifecycle](../architecture/settings-lifecycle.md) to see the full flow.
