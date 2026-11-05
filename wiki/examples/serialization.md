# Serialize and validate configuration documents

[formats.py](../../examples/formats.py) needs `confidantic[yaml,toml]`.
[serialization.py](../../examples/serialization.py) also displays its configuration,
so that script needs `confidantic[rich]`.

```console
uv run python examples/formats.py
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
