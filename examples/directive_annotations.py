# %% Imports -------------------------------------------------------------------------

"""Validate ordinary values or build them from portable call directives.

`Call` and `Make` pass ordinary values to Pydantic validation. Their call
directives import and invoke callables, so validate only trusted configuration
data when a document can contain `@call`.
"""

from collections.abc import Callable

from pydantic import BaseModel

from confidantic import BaseConfig
from confidantic.annotations import Call, Import, Make

# %% Resolve an import string without calling it ------------------------------------


# `Import[T]` validates an import string as T and serializes it back as a string.
class ImportConfig(BaseModel):
    """A callable selected by its stable import path."""

    measure: Import[Callable]


import_config = ImportConfig(measure="builtins:len")
print(import_config.measure(["one", "two", "three"]))
print(import_config.model_dump())

assert import_config.measure is len
assert import_config.model_dump() == {"measure": "builtins:len"}


# %% Call one imported function during validation -----------------------------------


# `@args` supplies positional arguments; other mapping entries become keyword args.
class CallConfig(BaseModel):
    """A value produced while validating trusted input."""

    greeting: Call[str]


call_config = CallConfig(
    greeting={
        "@call": "operator:concat",
        "@args": ["Hello, ", "world!"],
    }
)
print(call_config.greeting)

assert call_config.greeting == "Hello, world!"


# %% Validate ordinary values without a directive -----------------------------------


# Without `@call`, `T` describes the value Pydantic validates and returns.
class DirectValueConfig(BaseModel):
    """Ordinary values that may also be supplied by trusted directives."""

    retries: Call[int]
    labels: Call[dict[str, str]]
    timeout: Make[int]
    metadata: Make[dict[str, str]]


direct_values = DirectValueConfig(
    retries=3,
    labels={"environment": "development"},
    timeout=30,
    metadata={"owner": "platform"},
)
print(direct_values.model_dump())

assert direct_values.model_dump() == {
    "retries": 3,
    "labels": {"environment": "development"},
    "timeout": 30,
    "metadata": {"owner": "platform"},
}


# %% Recursively make values inside nested mappings ---------------------------------


# `Make[T]` traverses mappings and sequences, invoking every mapping with `@call`.
class MakeConfig(BaseModel):
    """Service definitions assembled from a configuration document."""

    services: Make[dict[str, list[dict[str, str | int]]]]


make_config = MakeConfig(
    services={
        "workers": [
            {"@call": "builtins:dict", "name": "api", "port": 8000},
            {"@call": "builtins:dict", "name": "jobs", "port": 8001},
        ]
    }
)
print(make_config.services)

assert make_config.services == {
    "workers": [
        {"name": "api", "port": 8000},
        {"name": "jobs", "port": 8001},
    ]
}


# %% Preserve concrete BaseConfig types through a document --------------------------


class ServiceConfig(BaseConfig):
    """Common settings for one service."""

    name: str


class HttpServiceConfig(ServiceConfig):
    """Settings specific to an HTTP service."""

    url: str
    timeout: float = 1.0


class ApplicationConfig(BaseConfig):
    """Application settings with a concrete service implementation."""

    service: Make[ServiceConfig]


class ConfigDocument(BaseModel):
    """Trusted portable document that reconstructs an application config."""

    application: Make[ApplicationConfig]


# %% Serialize with Make directives, then reconstruct the same concrete type -------

# `make=True` writes an importable class directive for BaseConfig instances.
application = ApplicationConfig.model_validate(
    {
        "service": {
            "@call": "__main__:HttpServiceConfig",
            "name": "api",
            "url": "https://api.example.test",
        }
    }
)
serialized = application.model_dump(context={"make": True}, serialize_as_any=True)
restored = ConfigDocument.model_validate({"application": serialized}).application

print(serialized)
print(type(restored.service).__name__)

assert type(restored) is ApplicationConfig
assert type(restored.service) is HttpServiceConfig
assert restored.model_dump(serialize_as_any=True) == application.model_dump(
    serialize_as_any=True
)

# %% ---------------------------------------------------------------------------------
