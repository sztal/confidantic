# %% Define nested model types -------------------------------------------------------

"""Use regular Pydantic models as fields inside a configuration.

The default factory creates a concrete subclass while the public annotation
continues to accept the base model type.
"""

from pydantic import BaseModel, Field

from confidantic import BaseConfig


class Coordinates(BaseModel):
    """Common coordinates shared by each nested variant."""

    x: int = 1
    y: int = 1


class OffsetCoordinates(Coordinates):
    """A concrete default with a different vertical coordinate."""

    y: int = 2


class Config(BaseConfig, cli_parse_args=True):
    """Configuration containing a nested Pydantic model."""

    coordinates: Coordinates = Field(
        default_factory=OffsetCoordinates,
        description="Coordinates used by the application.",
    )


# %% Inspect the concrete nested default ---------------------------------------------

# `info()` displays settings in the same way it does for scalar configuration fields.
config = Config()
config.info()

assert isinstance(config.coordinates, OffsetCoordinates)
assert config.coordinates.x == 1
assert config.coordinates.y == 2

# %% ---------------------------------------------------------------------------------
