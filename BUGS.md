# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

## Pages deployment can fail immediately after uploading its artifact

The former upload and deployment steps in `.github/workflows/pages.yaml` ran in
the same job, with no retry of a failed artifact lookup. In the
[v0.3.0 publication run](https://github.com/sztal/confidantic/actions/runs/45632275329),
the upload succeeded at 14:19:09 UTC on 2026-11-25, but the immediately following
deployment could not find an artifact named `github-pages`. GitHub's run artifact
list subsequently showed that artifact, and the overall publication workflow
failed even though PyPI publication and GitHub release creation succeeded.

An artifact visibility race is likely, but not proven by the available logs; an
[upstream report](https://github.com/actions/deploy-pages/issues/451) describes the
same intermittent failure when upload and deployment are consecutive steps.
The current workflow separates build and deployment, uses attempt-specific
artifact names, and retries deployment without re-uploading. It retains Pages
artifacts for seven days for deploy-only recovery. These mitigations still need
verification in a real GitHub Actions deployment and deploy-only rerun before this
entry can be resolved. Bounded retries cannot guarantee that GitHub's artifact
service is available. The old run retains its original combined workflow; rerunning
that job can create multiple artifacts with the same name in one workflow run.

## Nested model partial updates lose per-call validation options

Partial updates to an existing nested model call `_NestedModelUpdates._update_model`, which
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

Executable reproductions are in
`tests/_config/test_nested.py::test_nested_updates_forward_validation_options`.
They cover static and factory defaults for strictness, context, and both extra
policies. Partial updates are marked as strict expected failures; the same cases
with partial updates disabled must pass. An unexpected pass requires removing
the corresponding expected-failure marker when the source defect is fixed.
