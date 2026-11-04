# %% Create a temporary structured settings file ------------------------------------

"""Place a TOML source explicitly between initializer and environment sources."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

from confidantic import BaseConfig, ConfigModelDict

with TemporaryDirectory() as directory:
    config_path = Path(directory) / "settings.toml"
    config_path.write_text('host = "file.example.com"\nport = 9000\n', encoding="utf-8")

    class Config(BaseConfig):
        """Service settings with an explicit position for a TOML source."""

        model_config = ConfigModelDict(toml_file=config_path)

        host: str = "localhost"
        port: int = 8000

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            """Return sources in descending priority for this MRO level.

            Parameters
            ----------
            settings_cls
                Class whose settings are being resolved.
            init_settings, env_settings, dotenv_settings, file_secret_settings
                Standard sources supplied by Pydantic Settings.

            Returns
            -------
            tuple[PydanticBaseSettingsSource, ...]
                Initializer, TOML, environment, dotenv, and secret sources.
            """
            return (
                init_settings,
                TomlConfigSettingsSource(settings_cls),
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )

    # %% File values override defaults; initializer values override the file --------

    from_file = Config()
    overridden = Config(host="caller.example.com")
    assert from_file.host == "file.example.com"
    assert from_file.port == 9000
    assert overridden.host == "caller.example.com"
    assert overridden.port == 9000
    assert from_file.model_field_sources["host"] == (TomlConfigSettingsSource, Config)
    print(from_file.model_dump())
    print(overridden.model_dump())
