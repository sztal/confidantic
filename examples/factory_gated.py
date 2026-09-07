# %% Define a selectable implementation ---------------------------------------------

"""Route help, select an implementation, then configure its constructor.

The script demonstrates a staged CLI for applications whose final options depend
on a runtime-selected type:

1. ``HelpRouter`` decides whether ``--help`` describes type selection or the
   final generated configuration.
2. ``Types`` accepts an estimator import string through ``FactoryField`` and
   retains the selected value as a generated ``Factory`` class. Its default is
   generated from a template object, so it can provide nonstandard constructor
   defaults.
3. ``Config`` uses that generated class for a nested factory instance. The
   selected constructor parameters become ordinary CLI options, and the validated
    factory can resolve the final estimator object.

Run the default implementation with its template defaults::

    python examples/factory_gated.py

Override options generated from the default ``MovingAverage`` constructor::

    python examples/factory_gated.py \
        --estimator.window 10 --estimator.center

Select an implementation by import string and configure options unique to it::

    python examples/factory_gated.py \
        --types.estimator __main__:ExponentialMovingAverage \
        --estimator.window 12 --estimator.decay 0.85

Show final configuration help. Its estimator options reflect the type selected
by ``--types.estimator``::

    python examples/factory_gated.py --help

    python examples/factory_gated.py \
        --types.estimator __main__:ExponentialMovingAverage --help

Route ``--help`` to the type-selection gate instead. ``--help.types`` is consumed
by ``HelpRouter`` and causes ``Types`` to display ``--types.estimator`` before the
final configuration is parsed::

    python examples/factory_gated.py --help --help.types
"""

from confidantic import BaseConfig, Factory, FactoryField


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

    estimator: FactoryField[MovingAverage] = Factory.model_from(
        MovingAverage(window=20)
    )
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


config = Config.model_validate({"estimator": {"center": True}})
config.info()
resolved = config.model_resolve()

print(resolved.estimator)

# %% ---------------------------------------------------------------------------------
