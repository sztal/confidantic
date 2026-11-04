# Configuration models

Use `BaseConfig` for validated application settings assembled from several sources.
It extends Pydantic Settings, so ordinary Pydantic fields, constraints, aliases,
validators, and serialization remain available. A plain Pydantic BaseModel is still
appropriate for data that should not consult settings sources.

## Describe the inputs

Declare typed fields with defaults or leave them required. `ConfigModelDict` carries
settings options and Confidantic's additional options; general Pydantic model options
remain available. Supported settings controls can also be supplied with leading
underscores at construction. Each subclass contributes its own source policy through
[inheritance](sources-and-inheritance.md).

Defaults are validated. Source assembly precedes user model validators, so those
validators see merged inputs. Per-call validation options normally reach the active
validation chain; custom constructors retain upstream limitations, and
[nested reconstruction](nested-configuration.md) has a separate boundary.

Field descriptions can come from `Field(description=...)` or attribute docstrings.
Extraction is enabled outside notebook-like runtimes by default. An `@attrs` marker
in a class Attributes section requests generated documentation and requires the
`docstrings` extra. Unmarked class docstrings do not need that extra.

## Freezing and updates

Frozen fields prevent reassignment but do not make nested lists or objects immutable.
Choose the operation according to the required ownership and validation:

| Operation             | Behavior                                                 |
| --------------------- | -------------------------------------------------------- |
| `copy()`              | Structural shallow copy; nested values remain shared     |
| `deepcopy()`          | Structural deep copy                                     |
| `copy(**updates)`     | Revalidate stored values plus updates as a new instance  |
| `deepcopy(**updates)` | Deep-copy existing state, then apply validated updates   |
| `mutate(**updates)`   | Validate updates, then install them on the same instance |

Updated copies can consult sources again and rerun non-idempotent validators.
They are different from unchecked `model_copy(update=...)`. Do not mutate an object
while relying on its hash as a dictionary key or set member.

`model_info()` describes declared fields; `info()` displays stored values. Both need
Rich in all output modes. Source provenance is available separately through
`model_field_sources`.

Continue with [defining configuration](../examples/defining-config.md),
[BaseConfig internals](../api/_config/base.md), or [all concepts](README.md).
