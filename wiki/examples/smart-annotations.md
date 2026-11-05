# Use smart annotations

Use annotations to adapt deployment-friendly input while validating the resulting
Python values. The import/directive scripts need core Confidantic; the delimited
script also calls `info()` and therefore needs `confidantic[rich]`.

```console
uv run python examples/delimited.py --ports '[8000, 9000]' --features api --features worker --options 'retries=3,mode=debug'
uv run python examples/import_directive.py
uv run python examples/directive_annotations.py
```

## Collections and mappings

Excerpt from [delimited.py](../../examples/delimited.py), inside its Config class:

```python
ports: CommaDelimited[list[int]] = (8000,)
"""HTTP ports supplied as a comma-delimited environment value or CLI list."""
features: CommaDelimited[list[str]] = ()
"""Enabled features supplied as a comma-delimited environment value or CLI list."""
options: Map[dict[str, int | str]] = Field(default_factory=dict)
"""Options supplied as comma-separated key-value environment values or CLI input."""
```

The command displays ports 8000/9000, features api/worker, and the supplied mapping.
Environment strings can use comma-delimited values directly; CLI lists also accept
standard Pydantic Settings repeated or JSON-like input. Use JSON when data contains
separator characters that the simple text syntax cannot escape.

## Imports and calls

[import_directive.py](../../examples/import_directive.py) checks that a Counter class
and `"collections:Counter"` produce the same imported class. Import does not construct it.
The [directive script](../../examples/directive_annotations.py) then demonstrates a
call. This excerpt follows its CallConfig definition:

```python
call_config = CallConfig(
    greeting={
        "@call": "operator:concat",
        "@args": ["Hello, ", "world!"],
    }
)
```

The result is `"Hello, world!"`. Later assertions cover ordinary scalar inputs and
Make's recursive call mappings. Executable directives require trusted data.
For paths, `AbsolutePath` adds resolution to a path annotation; use
[the path guide](paths.md) when you need roots and anchors.

Read [input annotations](../concepts/input-annotations.md),
[annotation internals](../api/annotations.md), and [all guides](README.md).
