# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

## Attribute-docstring inspection during class reconstruction (fixed; cleanup pending)

With affected Pydantic versions, a class defined in a module unavailable to a
worker can fail cloudpickle
restoration with `TypeError: <class 'unavailable_worker_module.Config'> is a built-in class`. Observed with Python 3.13.9, Pydantic 2.13.4, and cloudpickle
3.1.2. This reduced reproduction also fails without Confidantic:

```python
import cloudpickle
from pydantic import BaseModel, ConfigDict


class Parent(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)


class Config(Parent):
    value: int = 1


Config.__module__ = "unavailable_worker_module"
cloudpickle.loads(cloudpickle.dumps(Config()))
```

Expected: unavailable source should not prevent reconstructing an otherwise
serializable configuration class. The confirmed cause is Pydantic's attribute
source inspection catching
`OSError` but not the `TypeError` raised when a reconstructed class's module is
unavailable. Catching both exceptions at source retrieval fixes the standalone
reproduction in an isolated process. The failure also reproduces on Pydantic
2.13.5 / Pydantic-core 2.46.5.
Confidantic inherits this failure when attribute-docstring extraction is enabled.
Setting `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS=false` before importing the package
in the producer and workers is a workaround, not a fix to Pydantic inspection.

A complete producer/worker reproduction, verified versions, proposed narrow
upstream fix, and related-issue search are in the
[prepared Pydantic issue report](reports/pydantic-attribute-docstrings-issue.md).
The defect is tracked upstream as
[Pydantic #13870](https://github.com/pydantic/pydantic/issues/13870).
Upstream fixed it in
[Pydantic #13874](https://github.com/pydantic/pydantic/pull/13874), released in
[Pydantic 2.14.0](https://github.com/pydantic/pydantic/releases/tag/v2.14.0).
Verified on 2026-10-27 with Python 3.13.9: fresh producer/worker reproductions with attribute
docstrings enabled fail for both plain Pydantic and Confidantic models on the
previously locked Pydantic 2.13.4, and pass on Pydantic 2.14.0 and 2.14.1.
The current dependency requirement is `pydantic>=2.14`, and `uv.lock` selects
2.14.1, so this defect is now fixed for supported installations. The worker
opt-out is no longer necessary for this specific failure. Entry removal and
workaround cleanup remain pending the required checks: the Nox typecheck
session currently reports incompatible optional annotations passed to
`TypeAdapter` in `confidantic/_config/base.py` (lines 493 and 498).

## Nested model partial updates lose per-call validation options

Partial updates to an existing nested model call `_update_nested_model`, which
starts another `model_validate` call without forwarding `strict`, `extra`, or
validation `context`. Moving outer settings assembly into the active validation
schema does not fix this separate reconstruction path.

```python
from pydantic import BaseModel, ValidationInfo, field_validator
from confidantic import BaseConfig


class Nested(BaseModel):
    count: int = 1

    @field_validator("count")
    @classmethod
    def offset(cls, value: int, info: ValidationInfo) -> int:
        return value + (info.context or {}).get("offset", 0)


class Config(BaseConfig):
    nested: Nested = Nested()


result = Config.model_validate(
    {"nested": {"count": "2"}}, strict=True, context={"offset": 10}
)
assert result.nested.count == 2
```

Expected: strict validation rejects the numeric string; with integer input,
the nested validator receives the supplied context and produces `12`. An
explicit extra policy should also reach nested reconstruction. Affected:
partial updates from mappings to default or lower-priority model instances,
including retained concrete subclasses. Disabling
`nested_model_default_partial_update` avoids this path but changes subtype and
baseline-value retention. This defect is deferred from the semantic-audit fixes.

Verified on 2026-10-27 with Python 3.13.9 and both Pydantic 2.13.4 and the updated
lock's 2.14.1: `strict=True` still accepts `"2"`, integer input with
`context={"offset": 10}` produces `2` instead of `12`,
and `extra="forbid"` silently drops unknown nested keys. Conversely,
`extra="ignore"` still raises when the nested model declares `extra="forbid"`.
The failures occur with static defaults and default factories, including
concrete subclass defaults. Disabling partial updates restores strictness,
context, and the per-call extra policy in the corresponding controls.
