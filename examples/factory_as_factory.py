"""Generate nested factories from a template object's constructor values."""
# %% ---------------------------------------------------------------------------------

from confidantic import Factory


class Database:
    """A small nested dependency."""

    def __init__(self, host: str, port: int = 5432) -> None:
        self.host = host
        self.port = port


_DEFAULT_DATABASE = Database("localhost")


class Application:
    """An application configured with a database dependency."""

    def __init__(
        self,
        name: str = "demo",
        database: Database = _DEFAULT_DATABASE,
    ) -> None:
        self.name = name
        self.database = database


template = Application("orders", Database("db.example.com", 6432))


class ApplicationConfig(
    Factory.model_from(template, as_factory=Database),
    cli_parse_args=True,
):
    """A configuration model for an application with a nested database."""


application = ApplicationConfig().model_resolve()

print(application.name)
print(application.database.host, application.database.port)

# %% ---------------------------------------------------------------------------------
