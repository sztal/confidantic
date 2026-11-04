# Customize settings sources

Use a custom source when input comes from an application-specific mechanism.
First read [sources](../guide/sources.md) and the
[TOML source recipe](../guide/files.md#use-a-toml-file-as-a-settings-source).
This example needs only core Confidantic.

## Insert application defaults

A source can be a callable returning a dictionary. This complete example represents
an application-selected deployment profile:

```python
from collections.abc import Callable
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from confidantic import BaseConfig, ConfigModelDict


def deployment_defaults() -> dict[str, Any]:
    """Supply the values selected by the application's deployment profile."""
    return {"name": "warehouse", "retries": 4}


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="APP_")

    name: str = "orders"
    retries: int = 3

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource | Callable[[], dict[str, Any]], ...]:
        """Place deployment defaults below explicit and environment inputs."""
        return (
            init_settings,
            env_settings,
            deployment_defaults,
            dotenv_settings,
            file_secret_settings,
        )


print(AppConfig().model_dump())
print(AppConfig(retries=6).model_dump())
```

With no matching environment variables, it prints:

```text
{'name': 'warehouse', 'retries': 4}
{'name': 'warehouse', 'retries': 6}
```

The tuple is descending priority within one class. CLI handling and inheritance
still follow Confidantic's normal rules. If a source performs I/O, remember that
it runs even when earlier sources already supplied all fields. Raise a clear error
when that input cannot be read or parsed; lower priority is not an error fallback.

## Retain provenance when needed

A bare callable disables automatic source provenance for the chain. Use a
`PydanticBaseSettingsSource` implementation when you need the standard source
interface and provenance support. Construct class-based sources with the hook's
`settings_cls`, so each inheritance level uses its own options and owner.

Built-in JSON, YAML, TOML, and pyproject sources already provide that interface.
Setting their filename options does not register them: include the source in the
returned tuple, as in the main files guide.

For more source combinations, read the
[wiki custom-source guide](https://github.com/sztal/confidantic/blob/master/wiki/examples/advanced/custom-sources.md)
and the [upstream settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
