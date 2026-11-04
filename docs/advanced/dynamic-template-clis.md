# Select a template before generating its CLI

When users can choose a dependency class, its configurable fields may be unknown
until that choice is made. Parse the type choice first, create a template, then
generate the final configuration and its CLI. Read [factories](../guide/factories.md)
and [command-line interfaces](../guide/cli.md) first. This example uses core
Confidantic and does not connect to a database.

Save this complete program as `app.py`:

```python
from confidantic import BaseConfig, ConfigModelDict, Factory
from confidantic.annotations import Import


class Database:
    def __init__(self, host: str = "localhost", port: int = 5432) -> None:
        self.host = host
        self.port = port


class ExtendedDatabase(Database):
    def __init__(
        self, host: str = "localhost", port: int = 5432, timeout: int = 10
    ) -> None:
        super().__init__(host, port)
        self.timeout = timeout


class Application:
    def __init__(self, name: str, database: Database) -> None:
        self.name = name
        self.database = database


class Types(BaseConfig):
    model_config = ConfigModelDict(
        cli_parse_args=True,
        cli_prefix="types",
        cli_help=False,
        cli_ignore_unknown_args=True,
    )

    database: Import[type[Database]] = Database


types = Types()
template = Application("orders", types.database())
ApplicationConfig = Factory.model_from(template, __recursive__=Database)


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(cli_parse_args=True)

    application: ApplicationConfig = ApplicationConfig()


config = AppConfig().model_resolve()
application = config.application
print(application.name)
print(type(application.database).__name__)
print(application.database.host, application.database.port)
```

```console
python app.py --types.database __main__:ExtendedDatabase --application.database.host db.example.com --application.database.timeout 20
```

```text
orders
ExtendedDatabase
db.example.com 5432
```

## Why there are two parsers

The first parser reads `--types.database` while ignoring final application options.
It suppresses standard help so `--help` reaches the final parser. After the selected
class is instantiated, its concrete template exposes fields such as `timeout`.
The selected database also receives `timeout=20`. The final parser also ignores unknown options by default, including the earlier
type-selection argument. With this staged policy, misspelled options may be ignored;
use the displayed help to check accepted names.

`Import[type[Database]]` validates the imported class's relationship to `Database`.
Importing can execute module code: the choice must come from trusted input. The
class also needs to be constructible without arguments at the template stage.
`__main__` works here because the chosen class is defined in the running script.
Use stable importable module names for reusable commands and documents.

## Recursive generation and resolution

`__recursive__=Database` selects matching concrete defaults for conversion to
nested factory fields. This is what makes dotted dependency options possible.
A type or type hint selects using the supported strict matching rules; a predicate
can inspect each whole default. Generation does not search individual collection
elements or invent values for required fields without defaults.

Resolution always traverses supported nested factory values, regardless of whether
`__recursive__` was used. Keep the distinction between generating nested fields
and constructing the resulting objects.

The [wiki dynamic-template guide](https://github.com/sztal/confidantic/blob/master/wiki/examples/advanced/dynamic-template-clis.md)
adds a help-routing stage and links to the tested repository example.
