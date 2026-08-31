# %% Imports and shared dotenv file -------------------------------------------------

"""Explore configuration sources and their precedence.

Run cells individually in VS Code's Python Interactive Window, or run this
file as a script. The assertions act as small, executable checkpoints.
"""

import os
from pathlib import Path

from confidantic import BaseConfig

dotenv_path = Path(__file__).with_name(".env")


# %% Load defaults from a dotenv file -----------------------------------------------


# `BaseConfig` reads CONFIG_NAME and CONFIG_NUMBER from the adjacent .env file.
class Config(BaseConfig, env_prefix="CONFIG_", env_file=dotenv_path):
    """Settings loaded from application inputs."""

    name: str
    """Human-readable application name."""
    number: int = 0
    """Example numeric setting."""


config = Config()
print(config)

assert config.name == "example"
assert config.number == 1


# %% Environment variables override dotenv values ----------------------------------

# Process-level configuration is useful for deployments and CI environments.
os.environ["CONFIG_NAME"] = "override"
config = Config()
print(config)

assert config.name == "override"
assert config.number == 1


# %% Initializer arguments have the highest priority --------------------------------

# Pass an explicit value when a caller must take precedence over external settings.
config = Config(name="init", number=2)
print(config)

assert config.name == "init"
assert config.number == 2


# %% Subclasses can use their own environment prefix --------------------------------


# This preserves inherited defaults while separating child-specific environment keys.
class ChildConfig(Config, env_prefix="CHILD_CONFIG_"):
    """A specialized configuration with its own environment namespace."""

    name: str = "child"


config = ChildConfig()
print(config)

assert config.name == "child"
assert config.number == 1


# %% Child environment variables take priority for the child class ------------------

os.environ["CHILD_CONFIG_NUMBER"] = "111"
config = ChildConfig()
print(config)

assert config.name == "child"
assert config.number == 111

# %% ---------------------------------------------------------------------------------
