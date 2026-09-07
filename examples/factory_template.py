# %% ---------------------------------------------------------------------------------

from confidantic import BaseConfig, Factory

# %% ---------------------------------------------------------------------------------


class Database:
    """A small nested dependency."""

    def __init__(self, host: str, port: int = 5432) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r})"


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
ApplicationConfig = Factory.model_from(template, as_factory=Database)

# %% ---------------------------------------------------------------------------------


class Config(BaseConfig, cli_parse_args=True):
    application: ApplicationConfig = ApplicationConfig()
    """A configuration model for an application with a nested database."""
    log_level: str = "INFO"
    """The log level for the application."""


config = Config().model_resolve()
config.info()

# %% --------------------------------------------------------------------------------
