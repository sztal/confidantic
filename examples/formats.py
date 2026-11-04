# %% Define a document model --------------------------------------------------------

"""Round-trip YAML and TOML using confidantic[yaml,toml]."""

from pydantic import Field, ValidationError

from confidantic import BaseConfig


class Config(BaseConfig):
    """Retry settings with a nullable label."""

    retries: int = Field(default=3, ge=0)
    label: str | None = None


config = Config(retries=5)

# %% YAML retains null values -------------------------------------------------------

yaml_text = config.model_dump_yaml()
from_yaml = Config.model_validate_yaml(yaml_text)
assert from_yaml.model_dump() == config.model_dump()
print(yaml_text.strip())

# %% TOML requires nullable fields to be omitted -------------------------------------

try:
    config.model_dump_toml()
except TypeError:
    pass
else:
    raise AssertionError("TOML cannot represent None")

toml_text = config.model_dump_toml(exclude_none=True)
from_toml = Config.model_validate_toml(toml_text)
assert "label" not in toml_text
assert from_toml.model_dump() == config.model_dump()
print(toml_text.strip())

# %% Parsed documents still undergo model validation --------------------------------

assert Config.model_validate_yaml('retries: "7"').retries == 7
assert Config.model_validate_toml('retries = "7"').retries == 7

try:
    Config.model_validate_yaml("retries: -1")
except ValidationError:
    pass
else:
    raise AssertionError("Document values must satisfy field constraints")

# exclude_none removes model fields, not None entries inside arbitrary containers.
