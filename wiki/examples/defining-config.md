# Define and update configuration

Use typed fields on BaseConfig to describe application inputs. The runnable
scripts need core Confidantic; the supplemental display example needs `rich`.
Run the complete scripts from the repository root:

```console
uv run python examples/basic.py
uv run python examples/config_updates.py
```

## Declare validated fields

[config_updates.py](../../examples/config_updates.py) uses this class. The excerpt
includes its imports and definition; subsequent excerpts use that same class.

```python
from pydantic import Field, ValidationError
from pydantic_settings import InitSettingsSource

from confidantic import BaseConfig, ClassDefaultsSource


class Config(BaseConfig):
    """Retry policy with a mutable collection inside a frozen model."""

    retries: int = Field(default=3, ge=0)
    """Number of retries after an initial attempt."""
    labels: list[str] = Field(default_factory=lambda: ["api"])
    """Labels retained by the retrying component."""
```

Defaults are validated, and normal field assignment is frozen. The list itself
remains mutable. The script verifies that `copy()` shares it while `deepcopy()`
duplicates it.

## Derive a validated replacement

Excerpt after `original = Config()`:

```python
updated = original.copy(retries=5)
assert original.retries == 3
assert updated.retries == 5
assert updated.model_field_sources["retries"] == (InitSettingsSource, Config)
assert updated.model_field_sources["labels"] == original.model_field_sources["labels"]
```

The script also checks that a negative retry count raises ValidationError and leaves
the original unchanged. It then deliberately calls `mutate(retries=1)` on the original.
Its stable output is:

```text
original=3, updated=5
mutated=1, updated=5
```

Updated copies run validation and configured sources again; they are not unchecked
dictionary replacements. Prefer copies when configurations are shared.
[basic.py](../../examples/basic.py) extends the same model pattern with dotenv,
environment input, and inheritance; it asserts each precedence step.

## Control display rows

Install `confidantic[rich]` for `model_info()` and `info()` in every output mode.
The following complete supplemental example is not part of the linked scripts:

```python
from pydantic import Field

from confidantic import BaseConfig


class DisplayConfig(BaseConfig):
    name: str = "orders"
    internal_label: str = Field("internal", repr=False)


config = DisplayConfig()
for render in (DisplayConfig.model_info, config.info):
    assert "internal_label" not in render(output="string")
    assert "internal_label" in render(output="string", respect_field_repr=False)
assert config.model_dump()["internal_label"] == "internal"
```

`model_info()` describes declared fields; `info()` shows stored values. Both omit
top-level `Field(repr=False)` rows by default. `respect_field_repr=False` includes
those rows, while nested objects retain their own representations.

This is display filtering, not serialization or a secrecy guarantee.
`Field(exclude=True)` controls serialization instead. See
[display tests](../../tests/_config/test_info.py) for the distinction.

Read [configuration models](../concepts/configuration-models.md) and
[BaseConfig internals](../api/_config/base.md). Continue to
[environment and dotenv](environment-and-dotenv.md), or return to [all guides](README.md).
