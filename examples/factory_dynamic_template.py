# %% ---------------------------------------------------------------------------------


from confidantic import BaseConfig, Factory

# %% ---------------------------------------------------------------------------------


class Database:
    """A small nested dependency."""

    def __init__(self, host: str = "localhost", port: int = 5432) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r})"


class ExtendedDatabase(Database):
    """An extended database with different class name."""

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

    template: bool = False
    """Whether to show the template help message."""


help_router = HelpRouter()

# %% ---------------------------------------------------------------------------------


class Types(
    BaseConfig,
    cli_parse_args=True,
    cli_help=help_router.template,
    cli_prefix="template",
    cli_ignore_unknown_args=True,
):
    """A configuration model for a types router."""

    # database: Make[Database] = Database()
    """A database dependency."""


types = Types()
template = Application("orders", types.database)
ApplicationConfig = Factory.model_from(template, __recursive__=Database)

# %% ---------------------------------------------------------------------------------


class Config(BaseConfig, cli_parse_args=True):
    application: ApplicationConfig = ApplicationConfig()
    """A configuration model for an application with a nested database."""
    log_level: str = "INFO"
    """The log level for the application."""


config = Config().model_resolve()
config.info()

# %% --------------------------------------------------------------------------------
