"""Run the first-application tutorial with core Confidantic.

Save this file as ``app.py`` and run ``python app.py``. An optional ``.env``
in the working directory supplies APP_NAME and APP_RETRIES; command-line
options such as ``--name shipping`` override those values.
"""

from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    """Settings for a small order-processing application."""

    model_config = ConfigModelDict(
        env_prefix="APP_",
        env_file=".env",
        cli_parse_args=True,
    )

    name: str = "orders"
    retries: int = 3


def main() -> None:
    """Read application settings and print their validated values."""
    config = AppConfig()
    print(config.model_dump())


if __name__ == "__main__":
    main()
