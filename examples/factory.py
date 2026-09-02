# %% Generate a configuration model from a constructor ------------------------------

"""Create an object from configuration derived from its constructor.

Run cells individually to inspect the generated model, then materialize the
target object from validated configuration values.
"""

from confidantic import BaseConfig, Factory


class Service:
    """A small application component with configurable constructor arguments."""

    def __init__(self, host: str = "localhost", port: int = 8000) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port})"


class Config(BaseConfig, cli_parse_args=True):
    """Application settings containing a configurable service."""

    service: Factory[Service] = Factory.instance_from(Service, port=9999)
    """Values passed to `Service` when it is materialized."""


# %% Inspect config fields, then materialize the target -----------------------------

config = Config(service={"host": "127.0.0.1"})
config.info()

service = config.service.materialize()
# OR just `service = config.service()` because `Factory` is callable.
print(service)

assert isinstance(service, Service)
assert service.host == "127.0.0.1"
assert service.port == 9999

# %% ---------------------------------------------------------------------------------
