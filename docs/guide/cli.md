# Add a command-line interface

A command-line interface (CLI) lets someone run your program with options such as
`--name shipping`. Confidantic uses the Pydantic Settings parser and validates the
result as ordinary settings.

## Options and nested fields

Save this as `app.py`:

```python
from pydantic import BaseModel

from confidantic import BaseConfig, ConfigModelDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(
        cli_parse_args=True,
        cli_ignore_unknown_args=False,
    )

    name: str = "orders"
    dry_run: bool = False
    database: Database = Database()


print(AppConfig().model_dump())
```

```console
python app.py --name shipping --dry-run true --database.host db.example.com
```

```text
{'name': 'shipping', 'dry_run': True, 'database': {'host': 'db.example.com', 'port': 5432}}
```

Underscores become hyphens in option names by default; nested fields use dots.
Boolean options take explicit values unless you enable `cli_implicit_flags`.
Use `python app.py --help` to see available options. Field descriptions and class
docstrings supply help text; environment names are hidden by default.

The example rejects unknown options so a typo is visible. Confidantic normally
ignores unknown arguments, which is useful for [staged parsers](../advanced/dynamic-template-clis.md).

!!! note "Choose where arguments are parsed"

    Enable CLI parsing on the root settings class. Only the most-derived class
    parses it within an inheritance chain. In notebook-like runtimes,
    `cli_parse_args=True` is ignored while `sys.argv` still belongs to the
    kernel launcher; explicit argument sequences and replaced `sys.argv`
    (such as IPython `%run`) are still parsed.

For tests, notebooks, or embedded usage, `cli_parse_args=["--name", "shipping"]`
supplies an explicit sequence. CLI values normally outrank initializer input
and other sources.

## Add a subcommand

A command such as `create demo` has its own fields. Save the following as `commands.py`:

```python
from pydantic_settings import CliPositionalArg, CliSubCommand, get_subcommand

from confidantic import BaseConfig, ConfigModelDict


class Create(BaseConfig):
    """Describe the project to create."""

    name: CliPositionalArg[str]
    dry_run: bool = False


class Commands(BaseConfig):
    model_config = ConfigModelDict(
        cli_parse_args=True,
        cli_ignore_unknown_args=False,
    )

    create: CliSubCommand[Create]


command = get_subcommand(Commands())
if isinstance(command, Create):
    print(command.name, command.dry_run)
```

```console
python commands.py create demo --dry-run true
```

```text
demo True
```

`CliPositionalArg` makes `name` positional; `CliSubCommand` selects a command model.
Keep `CliSubCommand` outermost in its annotation and do not assign a field default.
The root parses arguments; the command model does not need independent parsing.
Dispatching the selected command is your application's responsibility.

See [the options reference](../reference/options.md#command-line-options) for help
and parser controls, or [nested settings](nested-settings.md) for model composition.
