# Give an application object its own configuration

Use [Configurable][confidantic.configurable.Configurable] when you control a runtime
class and want it to retain explicit, validated settings. Use
[Factory](../guide/factories.md) when you want to derive settings from an existing
constructor instead. This recipe needs only core Confidantic.

```python
from confidantic.configurable import Configurable, InstanceConfig


class ServiceConfig(InstanceConfig):
    host: str = "localhost"
    port: int = 8000


class Service(Configurable):
    """A service that reads its address from retained configuration."""

    Config = ServiceConfig

    def address(self) -> str:
        """Return the configured address."""
        return f"{self.config.host}:{self.config.port}"


config = ServiceConfig(host="127.0.0.1", port=8080)
service = config.to_parent()
updated = service.copy(port=8081)
print(service.address())
print(updated.address())
```

```text
127.0.0.1:8080
127.0.0.1:8081
```

The direct `Config = ServiceConfig` declaration associates that configuration with
`Service`, enabling `to_parent()`. Construction also accepts mappings, Pydantic
models, or a compatible configuration instance. An existing compatible instance
is reused without updates; updates create a validated copy. Normal source priority
still applies when a new configuration is constructed.

## Make resource updates explicit

The example reads `self.config` every time `address()` runs. A connection or cache
created in a constructor behaves differently:

- `reconfigure()` and its `rc()` alias mutate the retained configuration without
    rerunning constructor setup. Other objects sharing the instance see the change.
- `copy(**updates)` constructs a new runtime object from copied configuration,
    then applies updates. Constructor-derived state can still reflect the earlier
    values.

If resources must be built with updated settings, construct from an updated
configuration explicitly, for example `service.config.copy(port=8081).to_parent()`.
Your runtime class remains responsible for closing and refreshing its resources.

## Persist the configuration

Continuing with the example:

```python
text = service.config.model_dump_json()
restored = ServiceConfig.model_validate_json(text).to_parent()
print(restored.address())
```

This prints `127.0.0.1:8080` and constructs a new runtime object. Keep handles and
caches outside the portable configuration. Runtime equality and hashing use the
configuration; pickle restoration installs configuration without calling the
runtime constructor.

A configuration's association is set by a direct `Config` declaration. Inheriting
`Config` does not change that association, and directly sharing the same
configuration class across several runtime classes assigns it to the last one.
Use distinct configuration classes when ownership differs.

See [configuration and objects](../concepts/configuration-and-objects.md) and the
[wiki reference](https://github.com/sztal/confidantic/blob/master/wiki/api/configurable.md)
for deeper lifecycle details.
