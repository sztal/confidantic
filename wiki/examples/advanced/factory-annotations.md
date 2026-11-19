# Resolve constructor annotations

Start with [the factory guide](../factories.md) and its runnable
[factory.py](../../../examples/factory.py). The complete snippets below supplement
that script; they are not part of its smoke tests. Run each snippet separately
from a Python file with core Confidantic installed.

## Supply a missing name

Factory generation evaluates constructor annotations at runtime. A name imported
only under `TYPE_CHECKING` may be unavailable then. Supply it explicitly:

```python
from pathlib import Path

from confidantic import Factory


class Exporter:
    """Write to a destination described by a runtime-resolved annotation."""

    def __init__(self, destination: "OutputPath", retries: int = 3) -> None:
        self.destination = destination
        self.retries = retries


try:
    Factory.model_from(Exporter)
except NameError:
    pass
else:
    raise AssertionError("Generation must reject the missing OutputPath name")

ExporterConfig = Factory.model_from(
    Exporter, __types_namespace__={"OutputPath": Path}
)
assert ExporterConfig.model_fields["destination"].is_required()
exporter = ExporterConfig(destination="output", retries="4").instance()
assert exporter.destination == Path("output")
assert exporter.retries == 4
```

Explicit names override automatic lookup in constructor globals and the target's
inheritance hierarchy. The mapping is shallow-copied; changing it afterward does
not alter the generated model's policy. It resolves symbolic names, not type
objects already present in annotations.

## Allow unresolved annotations

`__strict__=False` permits generation when annotations are missing or contain
unresolved names. This independent example uses an unannotated `label` parameter
deliberately to demonstrate that policy:

```python
from typing import Any

from confidantic import Factory


class Exporter:
    """Retain raw destinations while validating the annotated retry count."""

    def __init__(
        self, destination: "list[Missing]", label="daily", retries: int = 3
    ) -> None:
        self.destination = destination
        self.label = label
        self.retries = retries


ExporterConfig = Factory.model_from(Exporter, __strict__=False)
assert ExporterConfig.model_fields["destination"].annotation is Any
assert ExporterConfig.model_fields["destination"].is_required()
assert ExporterConfig.model_fields["label"].annotation is Any
assert ExporterConfig.model_fields["label"].default == "daily"
exporter = ExporterConfig(destination="raw destination", retries="4").instance()
assert exporter.destination == "raw destination"
assert exporter.label == "daily"
assert exporter.retries == 4
```

| Constructor annotation                     | Default `__strict__=True` | `__strict__=False`            |
| ------------------------------------------ | ------------------------- | ----------------------------- |
| Resolvable                                 | Use its type              | Use its type                  |
| Unresolved name                            | Raise `NameError`         | Use `Any` for the whole field |
| Missing annotation                         | Omit the parameter        | Include it as `Any`           |
| Malformed annotation or unsupported schema | Raise                     | Raise                         |

Fallback retains requiredness and defaults but does not validate or convert that
field. In particular, `list[Missing]` becomes `Any`, not `list[Any]`. Other fields
still validate normally. No warning is emitted for fallback.

This is annotation-resolution strictness, separate from Pydantic's validation
strictness. Variadic parameters are ignored. Positional-only parameters that
would become fields remain unsupported; exclude them and supply runtime inputs.

Both options work with `model_from()` and `instance_from()`. Recursive generation
passes them to nested factories. Generated models retain their policy for schema
rebuilds and target conversions; use the generated class as a field annotation
when that policy is needed. Plain `Factory[Target]` uses default strict resolution.

See the [published factory guide](../../../docs/guide/factories.md),
[builder reference](../../api/_config/_factory_build.md), and
[annotation-policy tests](../../../tests/_config/test_factory_build.py).
Return to [advanced guides](README.md).
