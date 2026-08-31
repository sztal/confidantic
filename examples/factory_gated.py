# %% Define a selectable implementation ---------------------------------------------

"""Select a target type first, then generate its configuration model.

This mirrors applications that use a small routing CLI before parsing the
selected implementation's options. The example is self-contained and needs
only Confidantic.
"""

from pydantic import Field, ImportString

from confidantic import BaseConfig, FactoryConfig


class MovingAverage:
    """A tiny selectable implementation with annotated constructor options."""

    def __init__(self, window: int = 20, center: bool = False) -> None:
        self.window = window
        self.center = center

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(window={self.window}, center={self.center})"


# %% Parse routing options without consuming implementation options -----------------


# A routing program could use `--help-types` before it knows the selected type.
class HelpRouter(
    BaseConfig,
    cli_parse_args=True,
    cli_prefix="help",
    cli_ignore_unknown_args=True,
):
    """Early CLI options that do not reject later configuration arguments."""

    types: bool = False
    """Whether to display available implementation types."""


help_router = HelpRouter()
print(help_router)


# %% Select an importable target type ------------------------------------------------


# In a real program, accept `--types-estimator package.module:Type` from the CLI.
class Types(
    BaseConfig,
    cli_parse_args=True,
    cli_prefix="types",
    cli_ignore_unknown_args=True,
):
    """Options used to choose which implementation will be configured."""

    estimator: ImportString[type[MovingAverage]]
    """Import path of the selected implementation class."""


types = Types(estimator="__main__:MovingAverage")
types.info()


# %% Generate and resolve settings for the selected type -----------------------------

# The selected constructor becomes a Pydantic model, including `window` and `center`.
EstimatorConfig = FactoryConfig.model_from(types.estimator)


class Config(
    BaseConfig,
    cli_parse_args=True,
    cli_ignore_unknown_args=True,
    arbitrary_types_allowed=True,
):
    """Final application settings, including the selected implementation."""

    estimator: EstimatorConfig = Field(default_factory=types.estimator)
    """Configuration values for the selected implementation."""
    parameter: float = 0.5
    """An ordinary application setting parsed after routing."""


config = Config(estimator={"window": 10, "center": True}).model_resolve()
config.info()

assert isinstance(config.estimator, MovingAverage)
assert config.estimator.window == 10
assert config.estimator.center is True

# %% ---------------------------------------------------------------------------------
