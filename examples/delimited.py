# %% Define delimited settings -------------------------------------------------------

"""Accept list and mapping settings from command-line arguments and environment variables.

Set comma-delimited environment or dotenv values, for example:
`APP_PORTS=8000,9000 APP_FEATURES=api,worker APP_OPTIONS=retries=3,mode=debug`
`python examples/delimited.py`.
Mapping pairs may also be separated by whitespace or end with a comma, for example:
`APP_OPTIONS='retries=3 mode=debug,' python examples/delimited.py`.

Pydantic Settings CLI list and mapping formats also work, for example:
`python examples/delimited.py --ports '[8000, 9000]' --features api --features worker`
`--options 'retries=3 mode=debug,'`.
"""

from pathlib import Path

from pydantic import Field

from confidantic import BaseConfig
from confidantic.annotations import CommaDelimited, Map

dotenv_path = Path(__file__).with_name(".env")


class Config(BaseConfig, cli_parse_args=True, env_file=dotenv_path, env_prefix="APP_"):
    """Application inputs available as lists and mappings from all supported sources."""

    ports: CommaDelimited[list[int]] = (8000,)
    """HTTP ports supplied as a comma-delimited environment value or CLI list."""
    features: CommaDelimited[list[str]] = ()
    """Enabled features supplied as a comma-delimited environment value or CLI list."""
    options: Map[dict[str, int | str]] = Field(default_factory=dict)
    """Options supplied as comma-separated key-value environment values or CLI input."""


# %% Resolve settings from CLI, environment, or dotenv ------------------------------

config = Config()
config.info()

# %% ---------------------------------------------------------------------------------
