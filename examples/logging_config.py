# %% Configure application logging ---------------------------------------------------

"""Configure console and rotating-file logging from settings.

Run cells in VS Code or execute this file. The rotating log is written to
`application.log` in the current working directory.
"""

import os
from pathlib import Path

from confidantic import BaseLogging

# %% Declare console and file settings -----------------------------------------------


# BaseLogging produces a standard logging.config.dictConfig-compatible setup.
class AppLogging(BaseLogging, env_prefix="EXAMPLE_LOG_"):
    """Logging settings for this application.

    Attributes
    ----------
    @attrs
    """

    file: Path = Path.cwd() / "application.log"
    """Rotating log file created in the current working directory."""
    file_level: str = "DEBUG"
    """File handler verbosity, independent from the console level."""


# %% Apply the configuration and emit records ----------------------------------------

# DEBUG is retained in the file; INFO appears in both the console and file.
logger = AppLogging(level="INFO").get_logger(__name__)
logger.debug("Written to the file but not the console.")
logger.info("Written to the console and file.")


# %% Override a setting through the environment --------------------------------------

# Deployment environments can set EXAMPLE_LOG_LEVEL without editing Python code.
os.environ["EXAMPLE_LOG_LEVEL"] = "warning"
config = AppLogging()

assert config.level == "WARNING"
assert config.file == Path.cwd() / "application.log"

# %% ---------------------------------------------------------------------------------
