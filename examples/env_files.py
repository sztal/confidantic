# %% Create temporary dotenv files --------------------------------------------------

"""Load configuration from explicit and automatically discovered dotenv files.

Run cells individually in VS Code's Python Interactive Window, or run this
file as a script. The temporary directory keeps the example self-contained.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from confidantic import BaseConfig, ConfigModelDict

with TemporaryDirectory() as directory:
    dotenv_directory = Path(directory)
    single_file = dotenv_directory / "single.env"
    shared_file = dotenv_directory / "shared.env"
    local_file = dotenv_directory / "local.env"
    discovered_file = dotenv_directory / ".env"

    single_file.write_text("SINGLE_NAME=from-single-file\n", encoding="utf-8")
    shared_file.write_text("MULTIPLE_NAME=from-shared-file\n", encoding="utf-8")
    local_file.write_text("MULTIPLE_NAME=from-local-file\n", encoding="utf-8")
    discovered_file.write_text("DISCOVERED_NAME=from-discovery\n", encoding="utf-8")

    class SingleFileConfig(BaseConfig):
        """Configuration loaded from one selected dotenv file."""

        model_config = ConfigModelDict(
            env_file=single_file,
            env_prefix="SINGLE_",
        )

        name: str

    config = SingleFileConfig()
    print(config)

    assert config.name == "from-single-file"

    class MultipleFilesConfig(BaseConfig):
        """Configuration loaded from ordered dotenv files."""

        model_config = ConfigModelDict(
            env_file=(shared_file, local_file),
            env_prefix="MULTIPLE_",
        )

        name: str

    config = MultipleFilesConfig()
    print(config)

    # Later files override values from earlier files.
    assert config.name == "from-local-file"

    class DiscoveredConfig(BaseConfig):
        """Configuration using an application-specific discovery strategy."""

        model_config = ConfigModelDict(
            env_file_discovery=True,
            env_prefix="DISCOVERED_",
        )

        name: str

        @classmethod
        def find_dotenv(cls) -> str:
            """Return the dotenv file selected by this application."""
            return str(discovered_file)

    config = DiscoveredConfig()
    print(config)

    assert config.name == "from-discovery"

# %% ---------------------------------------------------------------------------------
