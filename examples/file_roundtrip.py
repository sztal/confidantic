# %% Define a base configuration and a concrete subtype -----------------------------

"""Round-trip documents and load nested file-backed fields.

YAML and TOML writing require ``confidantic[yaml,toml]``. Constructor directives
are intended for trusted files and importable classes.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import Field

from confidantic import BaseConfig
from confidantic.annotations import FromJson, FromToml, FromYaml, Make


class Service(BaseConfig):
    """Common service settings."""

    name: str


class WebService(Service):
    """Service settings with a subtype-specific address."""

    host: str
    port: int = 8000


service = WebService(name="orders", host="localhost", port=8080)

# %% Round-trip ordinary values through a known model --------------------------------

assert (
    WebService.model_validate(service.model_dump()).model_dump() == service.model_dump()
)
assert (
    WebService.model_validate_json(service.model_dump_json()).model_dump()
    == service.model_dump()
)

# %% Load trusted files automatically inside a nested configuration ------------------

with TemporaryDirectory() as directory:
    root = Path(directory)
    json_path = root / "service.json"
    yaml_path = root / "service.yaml"
    toml_path = root / "service.toml"
    json_path.write_text(
        service.model_dump_json(context={"make": True}), encoding="utf-8"
    )
    yaml_path.write_text(
        service.model_dump_yaml(context={"make": True}), encoding="utf-8"
    )
    toml_path.write_text(
        service.model_dump_toml(context={"make": True}), encoding="utf-8"
    )

    class ServiceFiles(BaseConfig):
        """Service configurations loaded from three trusted documents."""

        json_service: Make[FromJson[Service]] = str(json_path)  # type: ignore[assignment]
        yaml_service: Make[FromYaml[Service]] = str(yaml_path)  # type: ignore[assignment]
        toml_service: Make[FromToml[Service]] = str(toml_path)  # type: ignore[assignment]
        raw_yaml: FromYaml = str(yaml_path)  # type: ignore[assignment]

    class Application(BaseConfig):
        """An application with a nested collection of file-backed fields."""

        services: ServiceFiles = Field(default_factory=ServiceFiles)

    application = Application()
    for loaded in (
        application.services.json_service,
        application.services.yaml_service,
        application.services.toml_service,
    ):
        assert type(loaded) is WebService
        assert loaded.model_dump() == service.model_dump()

    # Bare FromYaml returns the document without executing its @call directive.
    assert application.services.raw_yaml["@call"] == "__main__:WebService"
    loaded_yaml = application.services.yaml_service
    print(type(loaded_yaml).__name__, loaded_yaml.model_dump())
