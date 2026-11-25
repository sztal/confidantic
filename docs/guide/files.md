# Round-trip configuration documents and files

A configuration document is useful for saving values or exchanging them with
another program. Start with a known model class and a plain document:

```pycon
>>> from confidantic import BaseConfig
>>> class AppConfig(BaseConfig):
...     name: str = "orders"
...     retries: int = 3
>>> config = AppConfig(retries=5)
>>> text = config.model_dump_json()
>>> restored = AppConfig.model_validate_json(text)
>>> print(restored.model_dump())
{'name': 'orders', 'retries': 5}

```

`model_dump()` returns Python values; `model_dump_json()` returns JSON text.
To use a file, write that text with `Path.write_text(..., encoding="utf-8")` and
pass `Path.read_text(encoding="utf-8")` to the loader. Loading still validates
values against the model.

| Representation | Serialize                  | Validate as a known class             |
| -------------- | -------------------------- | ------------------------------------- |
| Python values  | `config.model_dump()`      | `AppConfig.model_validate(values)`    |
| JSON text      | `config.model_dump_json()` | `AppConfig.model_validate_json(text)` |
| YAML text      | `config.model_dump_yaml()` | `AppConfig.model_validate_yaml(text)` |
| TOML text      | `config.model_dump_toml()` | `AppConfig.model_validate_toml(text)` |

For example, continuing with `config` and `AppConfig`, a JSON file round trip is:

```python
from pathlib import Path

path = Path("config.json")
path.write_text(config.model_dump_json(), encoding="utf-8")
restored = AppConfig.model_validate_json(path.read_text(encoding="utf-8"))
assert restored.model_dump() == config.model_dump()
```

Compare dumped field values when checking a round trip. Model equality can also
reflect private state, such as whether values came from defaults or initializer
inputs. Dumping a model does not promise to preserve that source information.

## YAML and TOML

The examples below continue with `AppConfig` and `config` from above.

Install an optional writer to serialize configurations as YAML or TOML:

```console
pip install "confidantic[yaml]"
pip install "confidantic[toml]"
```

Both methods accept model-dump filtering, context, and serialization options
and return a string. Ordinary documents can be loaded directly:

```pycon
>>> yaml_text = config.model_dump_yaml()
>>> toml_text = config.model_dump_toml(exclude_none=True)
>>> loaded_yaml = AppConfig.model_validate_yaml(yaml_text)
>>> loaded_toml = AppConfig.model_validate_toml(toml_text)
>>> loaded_yaml.model_dump() == loaded_toml.model_dump() == config.model_dump()
True

```

YAML uses block formatting and preserves model field order, including a leading
Make directive. TOML has no null representation, so use `exclude_none=True` when
model fields can contain `None`. This does not remove `None` entries inside
lists or mappings; those require preprocessing. The YAML loader requires the
YAML extra; TOML loading uses Python's standard library. Both loaders parse into
Python values and forward their validation options to `model_validate()`.
Configured settings sources can still participate in construction, so loading
a document can use values from sources in addition to the document itself.
Per-call `strict`, `extra`, and field-validation `context` apply to validation of
the merged settings. Source assembly precedes user model validators.

Subclasses defining their own `__init__` retain Pydantic's custom-constructor
limitations on per-call validation options. The validation wrapper also retains
the upstream strict-JSON limitation for representations such as date strings
and tuple arrays: these can be rejected under `model_validate_json(strict=True)`.
YAML and TOML use Python-mode validation.

Partial updates to existing nested model instances still perform a separate
validation pass without forwarding per-call options. Disable
`nested_model_default_partial_update` when those options must apply throughout
nested validation; this also uses the annotated model type instead of retaining
a baseline instance's concrete subclass.

The loaders do not evaluate a root `@call` directive. For trusted documents that
choose constructors, parse the document and validate it through `Make` as shown
in [object directives and portability](../advanced/object-directives-and-portability.md#make-directives).

## File-backed fields

`FromJson`, `FromYaml`, and `FromToml` read UTF-8 files during field validation.
Without a type argument, each returns a mapping; a parameter such as
`FromYaml[AppConfig]` validates the file's mapping as that type. Use
`Make[FromYaml[AppConfig]]` to evaluate its directives first. YAML requires
`confidantic[yaml]`; JSON and TOML reading require no extra. All three require a
mapping at the document root. Strings and path-like values name files relative
to the current working directory; existing mappings and instances are also accepted.

For a portable subtype round trip, define the configuration classes in an
importable module available to both processes and write the producer's instance:

```python
from pathlib import Path

path = Path("component.yaml")
path.write_text(
    component.model_dump_yaml(context={"make": True}, serialize_as_any=True),
    encoding="utf-8",
)
```

Then the consumer can use that file as a default:

```python
from confidantic import BaseConfig
from confidantic.annotations import FromYaml, Make
from my_application import Component


class Settings(BaseConfig):
    component: Make[FromYaml[Component]] = "component.yaml"  # type: ignore[assignment]


component = Settings().component
```

Mypy needs the targeted ignore because the input default is a string while the
validated field has type `Component`. `BaseConfig` validates defaults; with an
ordinary Pydantic model, enable `validate_default` as needed.
Environment and CLI inputs can replace the entire field with another path.
Nested overrides replace the path default rather than merging with its file.

The same pattern works in more deeply nested settings and with the other file
formats. In this excerpt from
[file_roundtrip.py](https://github.com/sztal/confidantic/blob/master/examples/file_roundtrip.py),
`Service` is the base type and the paths contain `WebService` directives:

```python
class ServiceFiles(BaseConfig):
    json_service: Make[FromJson[Service]] = str(json_path)  # type: ignore[assignment]
    yaml_service: Make[FromYaml[Service]] = str(yaml_path)  # type: ignore[assignment]
    toml_service: Make[FromToml[Service]] = str(toml_path)  # type: ignore[assignment]


class Application(BaseConfig):
    services: ServiceFiles = Field(default_factory=ServiceFiles)


application = Application()
assert type(application.services.yaml_service) is WebService
```

Run the complete script with `uv run python examples/file_roundtrip.py` after
installing the YAML and TOML extras. It writes files in a temporary directory and
checks all three reconstructed types. Bare `FromYaml` instead returns the parsed
mapping, including `@call`, without executing it.

The resolved field contains the validated value, not its source path. Dumping
the containing model does not write back to the file. A normal dump without
`context={"make": True}` does not record the concrete class; it can still be
loaded as the declared type. Use directives only with trusted documents: they
can import and call arbitrary Python objects before type validation.

## Use a TOML file as a settings source

Loading a document explicitly is different from automatically consulting a file
when constructing settings. To do the latter, register the file's source.

Create `settings.toml` in the working directory:

```toml
name = "warehouse"
retries = 4
```

Save this as `app.py` and run it from that directory. Reading TOML needs only the
core package:

```python
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(toml_file="settings.toml")

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
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Place the TOML file after explicit Python inputs."""
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


print(AppConfig().model_dump())
print(AppConfig(name="shipping").model_dump())
```

```text
{'name': 'warehouse', 'retries': 4}
{'name': 'shipping', 'retries': 4}
```

The returned tuple lists sources from highest to lowest priority within this class.
The file comes before environment values here, although process environment loading
is disabled until you set a string `env_prefix`. Declared defaults remain fallbacks.
Merely setting `toml_file` would not register the source.

Use the hook's `settings_cls` argument when creating a source so inheritance uses
the correct class's options. JSON, YAML, and pyproject sources follow the same
registration pattern. Continue with [custom sources](../advanced/custom-sources.md)
when you need to implement your own input mechanism.
