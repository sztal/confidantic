# %% ---------------------------------------------------------------------------------

"""Select a dependency type before generating its nested CLI options.

Run with ``--types.database __main__:ExtendedDatabase`` to select the subclass.
The final parser accepts options such as ``--application.database.host localhost``.
``--help.types true --help`` displays the type selector's help; ``--help`` alone
displays the application options. Displaying values requires ``confidantic[rich]``.
"""

from confidantic import BaseConfig, Factory
from confidantic.annotations import Import

# %% ---------------------------------------------------------------------------------


class Database:
    """A small nested dependency."""

    def __init__(self, host: str = "localhost", port: int = 5432) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r})"


class ExtendedDatabase(Database):
    """Database variant with a class-level switch outside its constructor fields."""

    switch: bool = False
    """Extra database switch."""

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"switch={self.switch!r})"
        )


class Application:
    """An application configured with a database dependency."""

    def __init__(
        self,
        name: str = "demo",
        database: Database | None = None,
    ) -> None:
        self.name = name
        self.database = database or Database("localhost")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, database={self.database!r})"
        )


template = Application("orders", Database("db.example.com", 6432))
ApplicationConfig = Factory.model_from(template, __recursive__=Database)


# %% ---------------------------------------------------------------------------------


class HelpRouter(
    BaseConfig,
    cli_parse_args=True,
    cli_help=False,
    cli_prefix="help",
    cli_ignore_unknown_args=True,
):
    """A configuration model for a help router."""

    types: bool = False
    """Whether --help shows the dependency-type selector's options."""


help_router = HelpRouter()

# %% ---------------------------------------------------------------------------------


class Types(
    BaseConfig,
    cli_parse_args=True,
    cli_help=help_router.types,
    cli_prefix="types",
    cli_ignore_unknown_args=True,
):
    """A configuration model for a types router."""

    database: Import[type[Database]] = Database
    """A database dependency."""


types = Types()

# %% ---------------------------------------------------------------------------------

template = Application("orders", types.database())
ApplicationConfig = Factory.model_from(template, __recursive__=Database)

# %% ---------------------------------------------------------------------------------


class Config(BaseConfig, cli_parse_args=True):
    """Application inputs generated for the previously selected dependency type."""

    application: ApplicationConfig = ApplicationConfig()
    """A configuration model for an application with a nested database."""
    log_level: str = "INFO"
    """The log level for the application."""


config = Config().model_resolve()
config.info()

# %% --------------------------------------------------------------------------------
