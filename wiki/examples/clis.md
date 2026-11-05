# Define command-line interfaces

The [basic CLI script](../../examples/cli.py) requires `confidantic[rich]` for its
display step. The [subcommand script](../../examples/multilevel_cli.py) uses core
Confidantic and Pydantic Settings.

```console
uv run python examples/cli.py --name command-line --number 5
uv run python examples/multilevel_cli.py project create demo --dry-run true
uv run python examples/multilevel_cli.py project show
uv run python examples/multilevel_cli.py project --help
```

## Parse once at the root

The CLI script sets `cli_parse_args=True` on its model. The supplied command displays
`name="command-line"` and `number=5`, overriding its dotenv fixture.
Explicit booleans use a value by default, as in `--dry-run true`.

The multilevel script declares Create and Show models, groups them under Project,
and parses Program once. Excerpt after those command classes are defined:

```python
class Program(BaseConfig, cli_parse_args=True):
    """Top-level command-line interface."""

    project: CliSubCommand[Project]
```

It obtains the selected models with `get_subcommand(program)` and then
`get_subcommand(project)`. The create invocation prints:

```text
Would create project 'demo' in workspace 'default'.
```

The show invocation prints `Showing workspace 'default' with summary.` These are
simulated operations; they do not create a project. Help lists the command choices.

## Model the command structure

CliSubCommand and CliPositionalArg are Pydantic Settings annotations. Subcommand
fields have no defaults and use CliSubCommand as the outermost annotation. Missing
selection is handled by get_subcommand's policy. Unknown ordinary options are ignored
by Confidantic's default policy; unknown command tokens still fail parsing.

Nested configuration uses dotted field options. Continue to
[object templates](object-templates.md) to generate those fields from an object.
Read [CLI concepts](../concepts/clis.md) and
[parser internals](../api/_config/_cli.md), or return to [all guides](README.md).
