# Serialize and validate configuration documents

[formats.py](../../examples/formats.py) needs `confidantic[yaml,toml]`.
[file_roundtrip.py](../../examples/file_roundtrip.py) uses the same extras.
[serialization.py](../../examples/serialization.py) also displays its configuration,
so that script needs `confidantic[rich]`.

```console
uv run python examples/formats.py
uv run python examples/file_roundtrip.py
uv run python examples/serialization.py
```

## Ordinary format round trips

The format script defines a nonnegative retry count and nullable label. Excerpt
after `config = Config(retries=5)`:

```python
yaml_text = config.model_dump_yaml()
from_yaml = Config.model_validate_yaml(yaml_text)
assert from_yaml.model_dump() == config.model_dump()
print(yaml_text.strip())
```

YAML includes `label: null`. TOML cannot represent None, so its excerpt is:

```python
toml_text = config.model_dump_toml(exclude_none=True)
from_toml = Config.model_validate_toml(toml_text)
assert "label" not in toml_text
assert from_toml.model_dump() == config.model_dump()
print(toml_text.strip())
```

The missing label receives its model default on loading. Expected output is:

```text
retries: 5
label: null
retries = 5
```

Additional assertions verify coercion from document strings and rejection of a
negative count. Loading still performs model validation and can consult configured
settings sources. Excluding nullable model fields does not remove null list entries.
Use `model_dump()` and `model_validate()` for Python values, and `model_dump_json()`
and `model_validate_json()` for JSON text. When checking a round trip, compare
dumped field values; model equality can include private source-tracking state.

## Load files inside nested configuration

The file round-trip script writes a `WebService` instance to JSON, YAML, and TOML
in a temporary directory. Each dump uses `context={"make": True}`, which writes
an `@call` identifier for its concrete class. This excerpt uses its previously
defined models and paths:

```python
class ServiceFiles(BaseConfig):
    json_service: Make[FromJson[Service]] = str(json_path)  # type: ignore[assignment]
    yaml_service: Make[FromYaml[Service]] = str(yaml_path)  # type: ignore[assignment]
    toml_service: Make[FromToml[Service]] = str(toml_path)  # type: ignore[assignment]
    raw_yaml: FromYaml = str(yaml_path)  # type: ignore[assignment]


class Application(BaseConfig):
    services: ServiceFiles = Field(default_factory=ServiceFiles)


application = Application()
assert type(application.services.yaml_service) is WebService
```

The three `Make` fields load their files when `Application()` constructs the
nested settings, then evaluate their directives and validate the resulting
services. The bare `FromYaml` field returns the document mapping without executing
its directive. The script prints:

```text
WebService {'name': 'orders', 'host': 'localhost', 'port': 8080}
```

For transfer between processes, place `WebService` in an importable module shared
by both programs. The script's `__main__` identifier is suitable for its own
process. Relative paths use the working directory. The file path is an input;
dumping the application does not write the resolved values back to the files.
Only use `Make` with trusted data, because directives import and call Python code.

## Retain concrete configuration types

The serialization script uses `context={"make": True}` and `serialize_as_any=True`
to emit constructor directives and subclass values, then validates the mapping
through a Make-annotated document. It asserts restored nested types and equal data.
Ordinary nested BaseModel values have no directive; that example recovers their
concrete type through its configured baseline.

For portable identifiers and explicit nested construction, continue to
[portable object graphs](advanced/portable-object-graphs.md).
Read [serialization concepts](../concepts/serialization.md),
[format internals](../api/_config/_formats.md), or [all guides](README.md).
