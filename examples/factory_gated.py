# %% Define a selectable implementation ---------------------------------------------

"""Select a target type first, then generate its configuration model.

This mirrors applications that use a small routing CLI before parsing the
selected implementation's options. The example is self-contained and needs
only Confidantic.

Run the example with the default moving average and set its generated options::

    python examples/factory_gated.py \
        --types.estimator __main__:MovingAverage \
        --estimator.window 10 --estimator.center

Select a different implementation; its constructor adds the ``decay`` option::

    python examples/factory_gated.py \
        --types.estimator __main__:ExponentialMovingAverage \
        --estimator.window 12 --estimator.decay 0.85

The final configuration help shows the selected type's generated options::

    python examples/factory_gated.py --help

The routing stage can show help for choosing a type instead. It exits before
the final configuration is parsed::

    python examples/factory_gated.py --help.types
"""

from confidantic import BaseConfig, Factory


class MovingAverage:
    """A tiny selectable implementation with annotated constructor options."""

    def __init__(self, window: int = 20, center: bool = False) -> None:
        self.window = window
        self.center = center

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(window={self.window}, center={self.center})"


class ExponentialMovingAverage(MovingAverage):
    """A moving average with an additional smoothing factor."""

    def __init__(
        self,
        window: int = 20,
        center: bool = False,
        decay: float = 0.9,
    ) -> None:
        super().__init__(window=window, center=center)
        self.decay = decay

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(window={self.window}, "
            f"center={self.center}, decay={self.decay})"
        )


# %% Parse routing options without consuming implementation options -----------------


# A routing program could use `--help.types` before it knows the selected type.
class HelpRouter(
    BaseConfig,
    cli_prefix="help",
    cli_ignore_unknown_args=True,
    cli_help=False,
    cli_parse_args=True,
):
    """Early CLI options that do not reject later configuration arguments."""

    types: bool = False
    """Whether to display available implementation types."""


help_router = HelpRouter()
help_router.info()


# %% Select an importable target type ------------------------------------------------


# In a real program, accept `--types.estimator package.module:Type` from the CLI.
class Types(
    BaseConfig,
    cli_parse_args=True,
    cli_prefix="types",
    cli_ignore_unknown_args=True,
    cli_help=help_router.types,
):
    """Options used to choose which implementation will be configured."""

    estimator: Factory.Field[MovingAverage] = MovingAverage(window=20)
    # estimator: Import[type[MovingAverage]] = MovingAverage
    """Estimator to use."""


types = Types()
types.info()


# %% Convert the selected type to a factory ------------------------------------------


class Config(
    BaseConfig,
    cli_parse_args=True,
    cli_ignore_unknown_args=True,
    arbitrary_types_allowed=True,
):
    """Final application settings, including the selected implementation."""

    estimator: types.estimator = types.estimator()
    """Configuration values for the selected implementation."""
    parameter: float = 0.5
    """An ordinary application setting parsed after routing."""


config = Config(estimator={"center": True})
config.info()
estimator = config.estimator.materialize()

print(estimator)

# %% ---------------------------------------------------------------------------------
