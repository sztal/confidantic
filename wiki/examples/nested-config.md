# Nest configuration with concrete defaults

[nested.py](../../examples/nested.py) uses an ordinary Pydantic model inside
BaseConfig. Install `confidantic[rich]` for its display call, then run:

```console
uv run python examples/nested.py
```

The script defines Coordinates with `x=1, y=1` and an OffsetCoordinates subclass
whose `y` default is 2. This excerpt uses those classes:

```python
class Config(BaseConfig, cli_parse_args=True):
    """Configuration containing a nested Pydantic model."""

    coordinates: Coordinates = Field(
        default_factory=OffsetCoordinates,
        description="Coordinates used by the application.",
    )
```

The public annotation accepts Coordinates, while the default factory creates the
concrete OffsetCoordinates. The script asserts that the result retains that concrete
class and has `x=1, y=2`; the table displays the nested value.

## Understand partial updates

With partial updates enabled, mapping input can patch a concrete default model
while retaining its current values and subtype. Ordinary nested mappings merge
across sources too, but lists are replaced rather than concatenated. Discriminated
models select a replacement variant instead of patching another variant's baseline.

The example's assertions intentionally describe the default invocation. For a model
whose defaults should not act as baselines, disable
`nested_model_default_partial_update`; that also changes subtype retention.
The separate reconstruction pass has a current validation-option limitation linked
from [nested configuration](../concepts/nested-configuration.md).

For arbitrary non-Pydantic constructor objects, use
[factories](factories.md) and [object templates](object-templates.md).
Implementation and behavioral cases live in [\_nested](../api/_config/_nested.md)
and [nested tests](../../tests/_config/test_nested.py).
Return to [all guides](README.md).
