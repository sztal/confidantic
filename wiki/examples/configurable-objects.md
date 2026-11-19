# Define configurable runtime objects

[configurable.py](../../examples/configurable.py) needs core Confidantic. It defines
a ServiceConfig with host/port fields and binds it to a Service runtime class.

```console
uv run python examples/configurable.py
```

Excerpt after the InstanceConfig subclass is defined:

```python
class Service(Configurable):
    """A service constructed from :class:`ServiceConfig`."""

    Config = ServiceConfig

    def address(self) -> str:
        """Return the configured network address."""
        return f"{self.config.host}:{self.config.port}"
```

The direct Config declaration associates ServiceConfig with its parent. The script
then constructs the runtime object through the configuration:

```python
config = ServiceConfig(host="127.0.0.1", port=8080)
service = config.to_parent()
copy = service.copy(port=8081)
```

It prints and asserts these addresses:

```text
127.0.0.1:8080
127.0.0.1:8081
```

## Separate configuration from resources

The method reads configuration dynamically, so the copied object's updated port is
visible immediately. A constructor-built cache is different: copy updates happen
after construction, and reconfigure does not rerun the constructor. Resource refresh
belongs to the runtime class.

For persistence, dump the concrete ServiceConfig, validate it on loading, and call
to_parent to create fresh resources. Runtime pickle state only retains configuration
and does not execute constructor setup on restoration. Existing configuration inputs
can be shared by reference, so deliberate mutation can affect multiple objects.

## Observe shared updates and constructor state

This complete supplemental example is separate from `configurable.py` and its
smoke test. The constructor captures a label once; the configuration remains a
live reference:

```python
from confidantic.configurable import Configurable, InstanceConfig


class ComponentConfig(InstanceConfig):
    name: str = "original"


class Component(Configurable):
    """Keep a constructor-time snapshot beside live configuration."""

    Config = ComponentConfig

    def __init__(self, config: ComponentConfig | None = None) -> None:
        super().__init__(config)
        self.initial_name = self.config.name


config = ComponentConfig()
first, second = Component(config), Component(config)
first.reconfigure(name="shared")
assert first.config is second.config is config
assert second.config.name == "shared"
assert first.initial_name == second.initial_name == "original"

for method in (first.copy, first.deepcopy):
    updated = method(name="copied")
    assert updated.config is not config
    assert updated.config.name == "copied"
    assert updated.initial_name == "shared"
assert config.name == "shared"
```

Reconfiguration changes the shared configuration without rerunning constructors.
Copying runs the constructor with copied configuration first, then applies the
updates. The snapshot therefore remains `"shared"` even though the copied
configuration says `"copied"`. A fresh `Component(ComponentConfig(name="copied"))`
would capture the new name during construction. See
[lifecycle tests](../../tests/test_configurable.py) for both copy variants.

Read [configured objects](../concepts/configured-objects.md),
[implementation details](../api/configurable.md), or [all guides](README.md).
