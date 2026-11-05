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

Read [configured objects](../concepts/configured-objects.md),
[implementation details](../api/configurable.md), or [all guides](README.md).
