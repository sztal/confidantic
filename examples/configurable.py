# %% Define an object with an instance configuration ---------------------------------

"""Define configurable classes with nested :class:`InstanceConfig` models.

The nested configuration validates construction input and can create its parent
object directly through :meth:`InstanceConfig.to_parent`.
"""

from confidantic.configurable import Configurable, InstanceConfig


class ServiceConfig(InstanceConfig):
    """Validated options for :class:`Service`."""

    host: str = "localhost"
    port: int = 8000


class Service(Configurable):
    """A service constructed from :class:`ServiceConfig`."""

    Config = ServiceConfig

    def address(self) -> str:
        """Return the configured network address."""
        return f"{self.config.host}:{self.config.port}"


# %% Configure and derive service instances ------------------------------------------

config = ServiceConfig(host="127.0.0.1", port=8080)
service = config.to_parent()
copy = service.copy(port=8081)

print(service.address())
print(copy.address())

assert service.address() == "127.0.0.1:8080"
assert copy.address() == "127.0.0.1:8081"

# %% ---------------------------------------------------------------------------------
