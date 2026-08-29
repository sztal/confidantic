# %% Generate a configuration model from a constructor ------------------------------

"""Create an object from configuration derived from its constructor.

Run cells individually to inspect the generated model, then materialize the
target object from validated configuration values.
"""

from pydantic import Field

from confidantic import BaseConfig, FactoryConfig


class Service:
    """A small application component with configurable constructor arguments."""

    def __init__(self, host: str = "localhost", port: int = 8000) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port})"


# `model_from()` reads the annotated constructor to create `ServiceConfig`.
ServiceConfig = FactoryConfig.model_from(Service)


class Config(BaseConfig, cli_parse_args=True):
    """Application settings containing a configurable service."""

    service: ServiceConfig = Field(default_factory=ServiceConfig)
    """Values passed to `Service` when configuration is resolved."""


# %% Inspect config fields, then materialize the target -----------------------------

# `model_resolve()` walks factory fields and replaces them with target objects.
config = Config(service={"host": "127.0.0.1", "port": 8080})
config.info()

resolved = config.model_resolve()
print(resolved.service)

assert isinstance(resolved.service, Service)
assert resolved.service.host == "127.0.0.1"
assert resolved.service.port == 8080

# %% ---------------------------------------------------------------------------------
