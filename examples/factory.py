# %% Define the target --------------------------------------------------------------

"""Generate configuration from a constructor or an existing object template."""

from dataclasses import dataclass

from pydantic import ValidationError

from confidantic import Factory


@dataclass
class Service:
    """Service address whose constructor supplies the configuration schema.

    Parameters
    ----------
    host
        Required server hostname.
    port
        Server port, defaulting to 8000.
    """

    host: str
    port: int = 8000


# %% Generate a class, validate its fields, then construct the target ----------------

ServiceConfig = Factory.model_from(Service)
assert ServiceConfig.model_fields["host"].is_required()

try:
    ServiceConfig()
except ValidationError:
    pass
else:
    raise AssertionError("The generated configuration must require host")

config = ServiceConfig(host="api.example.com", port=8080)
assert isinstance(config, Factory)
service = config.instance()
assert isinstance(service, Service)
assert service == Service("api.example.com", 8080)
print(service)

# %% Capture defaults from an instance ----------------------------------------------

template = Service("template.example.com", 9000)
TemplateConfig = Factory.model_from(template)
configured = TemplateConfig(port=9001)
assert configured.host == "template.example.com"
assert configured.instance() == Service("template.example.com", 9001)
assert template.port == 9000

# %% Generate and instantiate in one call -------------------------------------------

shortcut = Factory.instance_from(Service, host="worker.example.com")
assert shortcut.instance() == Service("worker.example.com", 8000)
print(shortcut.instance())

# Runtime-only inputs can be excluded from the configuration schema.
PortConfig = Factory.model_from(Service, __exclude__={"host"})
partial = PortConfig(port=9000)
assert partial.instance("runtime.example.com") == Service("runtime.example.com", 9000)
assert partial.instance("runtime.example.com", port="9001").port == "9001"
assert partial.copy(port="9001").instance("runtime.example.com").port == 9001
assert isinstance(partial.model_resolve(), Factory)
