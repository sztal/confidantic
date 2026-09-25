# %% Define commands and their arguments --------------------------------------------

"""Build a nested command-line program with Pydantic Settings subcommands.

Run this file with one of the following command paths:

    python examples/multilevel_cli.py project create demo --dry-run true
    python examples/multilevel_cli.py project show

Use `--help` after any command level to inspect the commands available there.
For example, `python examples/multilevel_cli.py project --help` lists `create`
and `show`.
"""

from pydantic_settings import CliPositionalArg, CliSubCommand, get_subcommand

from confidantic import BaseConfig


class Create(BaseConfig):
    """Create a project from a required positional name."""

    name: CliPositionalArg[str]
    """Name of the project to create."""
    dry_run: bool = False
    """Report the action without creating the project."""


class Show(BaseConfig):
    """Display the selected project workspace."""

    details: bool = False
    """Include detailed project information."""


# %% Group related commands under one subprogram ------------------------------------


# The field names become the positional command tokens: `project create` or
# `project show`. A command level can expose several CliSubCommand fields.
class Project(BaseConfig):
    """Commands that manage projects."""

    create: CliSubCommand[Create]
    show: CliSubCommand[Show]
    workspace: str = "default"
    """Workspace used by every project command."""


# %% Define the root program ---------------------------------------------------------


# `cli_parse_args=True` belongs on the root model. The first subcommand field name
# makes `project` the second token after the program executable.
class Program(BaseConfig, cli_parse_args=True):
    """Top-level command-line interface."""

    project: CliSubCommand[Project]


# %% Parse and dispatch the selected command -----------------------------------------

# CliSubCommand fields cannot have defaults and must be their outermost annotation.
# Consequently, a missing or unknown command exits with generated argparse help;
# do not use `CliSubCommand[Create] | None` to make a command optional.
program = Program()
project = get_subcommand(program)
command = get_subcommand(project)

if isinstance(command, Create):
    action = "Would create" if command.dry_run else "Creating"
    print(f"{action} project {command.name!r} in workspace {project.workspace!r}.")
elif isinstance(command, Show):
    detail_level = "with details" if command.details else "with summary"
    print(f"Showing workspace {project.workspace!r} {detail_level}.")
else:  # pragma: no cover - the command annotation makes this exhaustive.
    raise TypeError(f"Unsupported command: {command!r}")

# %% ---------------------------------------------------------------------------------
