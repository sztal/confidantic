# Read and write configuration files

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
