# Accept convenient text inputs

Environment variables arrive as text. You may want `8000,9000` to become a list
of ports while still validating each port as an integer. Confidantic's annotations
add that parsing to ordinary typed fields.

## Lists and mappings

```python
from confidantic import BaseConfig
from confidantic.annotations import CommaDelimited, Map


class WorkerConfig(BaseConfig):
    ports: CommaDelimited[list[int]]
    limits: Map[dict[str, int]]


config = WorkerConfig(ports="8000,9000", limits="workers=4,retries=3")
print(config.model_dump())
```

```text
{'ports': [8000, 9000], 'limits': {'workers': 4, 'retries': 3}}
```

These annotations also work with Pydantic's `BaseModel` and `TypeAdapter`.
An executable example using a custom separator:

```pycon
>>> from pydantic import TypeAdapter
>>> from confidantic.annotations import Delimited
>>> TypeAdapter(Delimited("|")[list[int]]).validate_python("1 | 2")
[1, 2]

```

The parser first tries normal validation, then JSON, then delimiter splitting.
Item types still matter: a nonnumeric port fails validation. `Map` accepts ordinary
mappings, JSON objects, or key/value text; repeated keys keep the last value and
values split at the first equals sign.

!!! note "Use JSON for embedded separators"

    Delimited text does not provide quoting or escape syntax. Use JSON when an
    item contains the separator. Explicit separators preserve empty items;
    whitespace splitting collapses runs of whitespace.

The annotations carry `NoDecode` so settings sources can leave raw strings for
their validators. CLI parsing may normalize list or mapping syntax first, so a
CLI's accepted notation can differ from the equivalent environment variable.
See [the annotations reference](../reference/annotations.md) for the named aliases.

## Resolve a filesystem path

[AbsolutePath](../reference/annotations.md#paths) validates a
[pathlib.Path][] and resolves a relative value against the working directory.
It follows symlinks but does not expand `~`. Add a constraint such as
`AbsolutePath[FilePath]` when the path must already exist; the existence check
runs before resolution.

For application directories sharing a root, use the [paths recipe](../recipes/paths.md).
Importing or constructing objects from strings is a separate capability covered
in [object directives](../advanced/object-directives-and-portability.md).
