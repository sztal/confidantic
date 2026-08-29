# %% Define comma-delimited settings -------------------------------------------------

"""Accept list settings from command-line arguments and environment variables.

Set comma-delimited environment or dotenv values, for example:
`APP_PORTS=8000,9000 APP_FEATURES=api,worker python examples/delimited.py`.

Pydantic Settings CLI list formats also work, for example:
`python examples/delimited.py --ports '[8000, 9000]' --features api --features worker`.
"""

from pathlib import Path

from pydantic import Field

from confidantic import BaseConfig
from confidantic.annotations import CommaDelimited

dotenv_path = Path(__file__).with_name(".env")


class Config(BaseConfig, cli_parse_args=True, env_file=dotenv_path, env_prefix="APP_"):
    """Application inputs available as lists from all supported sources."""

    ports: CommaDelimited[list[int]] = (8000,)
    """HTTP ports supplied as a comma-delimited environment value or CLI list."""
    features: CommaDelimited[list[str]] = ()
    """Enabled features supplied as a comma-delimited environment value or CLI list."""
    options: dict[str, int | str] = Field(default_factory=dict)


# %% Resolve settings from CLI, environment, or dotenv ------------------------------

config = Config()
config.info()

# %% ---------------------------------------------------------------------------------
