# %% Define configuration and ordinary nested models ---------------------------------

"""Serialize nested configurations and restore them from portable data.

`BaseConfig` values can write `@call` directives with `make=True`. This is
designed for trusted documents because restoring a directive imports a class.
"""

from pydantic import BaseModel, Field

from confidantic import BaseConfig
from confidantic.annotations import Make


class NestedConfig(BaseConfig):
    """A nested configuration that supports Make serialization."""

    x: int = 1


class NestedModel(BaseModel):
    """An ordinary Pydantic model without a Make directive."""

    y: int = 2


class Config(BaseConfig):
    """Application configuration containing both model kinds."""

    sub: BaseConfig = Field(default_factory=NestedConfig)
    """Nested BaseConfig serialized with its concrete class directive."""
    model: BaseModel = Field(default_factory=NestedModel)
    """Ordinary Pydantic model serialized as data only."""


class ConfigDocument(BaseModel):
    """A trusted document containing a portable application configuration."""

    config: Make[Config]


config = Config(sub={"x": 11})
config.info()


# %% Write a readable portable document ----------------------------------------------

# `serialize_as_any=True` preserves values behind the broad BaseConfig/BaseModel hints.
document = config.model_dump_json(
    indent=2,
    context={"make": True},
    serialize_as_any=True,
)
print(document)

assert '"@call"' in document


# %% Validate the document back into the configuration -------------------------------

# `Make[Config]` consumes the root directive and restores concrete nested types.
dump = config.model_dump(context={"make": True}, serialize_as_any=True)
config_roundtrip = ConfigDocument.model_validate({"config": dump}).config

original = config.model_dump(serialize_as_any=True)
restored = config_roundtrip.model_dump(serialize_as_any=True)

assert type(config_roundtrip.sub) is NestedConfig
assert type(config_roundtrip.model) is NestedModel
assert original == restored

# %% ---------------------------------------------------------------------------------
