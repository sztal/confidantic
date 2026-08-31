# %% Define a command-line configuration --------------------------------------------

"""Inspect settings supplied through command-line arguments.

Run this file normally to use values from `.env`, or pass arguments such as:
`python examples/cli.py --name command-line --number 5`.
"""

from pathlib import Path

from confidantic import BaseConfig

dotenv_path = Path(__file__).with_name(".env")


# `cli_parse_args=True` lets Pydantic Settings read the current command line.
class Config(
    BaseConfig, cli_parse_args=True, env_file=dotenv_path, env_prefix="CONFIG_"
):
    """Settings available through both environment variables and CLI options."""

    name: str
    """Application name, supplied by the CLI or dotenv file."""
    number: int = 0
    """Example integer option."""
    mapping: dict[str, int] | None = None
    """Optional mapping accepted from a JSON-like CLI value."""
    sequence: list[int] | None = None
    """Optional sequence accepted from repeated or JSON-like CLI values."""


# %% Resolve and inspect the command-line configuration -----------------------------

# CLI values override dotenv values; `info()` shows the resolved value and its source.
config = Config()
config.info()

# %% ---------------------------------------------------------------------------------
