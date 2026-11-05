# %% Define validated configuration ------------------------------------------------

"""Copy and update frozen configurations while inspecting field provenance."""

from pydantic import Field, ValidationError
from pydantic_settings import InitSettingsSource

from confidantic import BaseConfig, ClassDefaultsSource


class Config(BaseConfig):
    """Retry policy with a mutable collection inside a frozen model."""

    retries: int = Field(default=3, ge=0)
    """Number of retries after an initial attempt."""
    labels: list[str] = Field(default_factory=lambda: ["api"])
    """Labels retained by the retrying component."""


original = Config()
assert original.model_field_sources["retries"] == (ClassDefaultsSource, Config)

# %% Structural copying preserves or duplicates nested values -----------------------

shallow = original.copy()
deep = original.deepcopy()
assert shallow is not original
assert shallow.labels is original.labels
assert deep.labels == original.labels
assert deep.labels is not original.labels

# %% Updates create a validated replacement -----------------------------------------

updated = original.copy(retries=5)
assert original.retries == 3
assert updated.retries == 5
assert updated.model_field_sources["retries"] == (InitSettingsSource, Config)
assert updated.model_field_sources["labels"] == original.model_field_sources["labels"]

try:
    original.copy(retries=-1)
except ValidationError:
    pass
else:
    raise AssertionError("Negative retries must fail validation")

assert original.retries == 3
print(f"original={original.retries}, updated={updated.retries}")

# %% Explicit mutation updates the same instance ------------------------------------

assert original.mutate(retries=1) is original
assert original.retries == 1
assert updated.retries == 5
print(f"mutated={original.retries}, updated={updated.retries}")

# Frozen fields do not make nested lists immutable. Prefer replacements when sharing
# configurations, and do not mutate a configuration used as a dictionary key.
