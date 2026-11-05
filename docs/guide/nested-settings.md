# Group related settings

A growing application often has database, worker, and logging settings. A nested
model keeps those groups understandable and exposes individual fields to validation.
Use an ordinary Pydantic model for a group that should receive its inputs from the
outer configuration:

```python
from pydantic import BaseModel

from confidantic import BaseConfig, ConfigModelDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="APP_")

    database: Database = Database()


config = AppConfig(database={"host": "db.example.com"})
print(config.database.model_dump())
```

```text
{'host': 'db.example.com', 'port': 5432}
```

Only the host changed. A nested `BaseConfig` is also possible when the nested
component needs settings-source behavior of its own.

## Override a nested field externally

The default environment delimiter is `__`, so `APP_DATABASE__PORT=6543` addresses
the nested port. With CLI parsing enabled on the outer model,
`--database.port 6543` addresses the same field. In the example above, the explicit
Python host and an environment port can combine because they supply different keys.

## Mappings, lists, and existing models

Mappings from different sources merge recursively: a lower-priority mapping fills
keys that a higher-priority mapping did not supply. Lists and other non-mapping
values are replaced rather than concatenated.

An existing default model can supply more than the defaults of its annotation:

```pycon
>>> from pydantic import BaseModel
>>> from confidantic import BaseConfig
>>> class Database(BaseModel):
...     host: str = "localhost"
...     port: int = 5432
>>> class AppConfig(BaseConfig):
...     database: Database = Database(host="production.example.com", port=6432)
>>> config = AppConfig(database={"port": 6543})
>>> config.database.host, config.database.port
('production.example.com', 6543)

```

Partial updates to nested defaults are enabled by default. A mapping patches the
existing model's stored values and validates a new instance. If the default is a
subclass, its concrete type and extra subclass fields can be retained. Serializers
do not define the values used as this baseline.

Set `nested_model_default_partial_update=False` in `ConfigModelDict` to build from
the supplied mapping and annotated type instead. In the example, that would use
`Database`'s own default host, `localhost`.

!!! warning "Per-call validation options and partial updates"

    Reconstruction of an existing nested model currently does not forward outer
    per-call `strict`, `extra`, or field-validation `context`. Disable
    `nested_model_default_partial_update` when those options must apply throughout.
    This also changes baseline and subclass retention, as described above.

Ordinary `Field(default_factory=...)` values are evaluated lazily during validation.
Their source-level default blocks lower-priority values for the whole field; they
are not eager instances available for partial merging. Generated copied-default
wrappers used by factories have their own template-aware handling. Discriminated
unions replace a different selected variant instead of patching its old instance.

Continue with [input parsing](input-parsing.md) or the explanation of
[values and inheritance](../concepts/values-and-inheritance.md).
