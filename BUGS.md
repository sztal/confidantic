# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

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

## Default environment prefix breaks supplied CLI source construction

Creating a Pydantic Settings `CliSettingsSource` for a default `BaseConfig`
subclass raises `TypeError: object of type 'NoneType' has no len()` before the
source can be supplied to the model. `BaseConfig` enables `cli_show_env_vars`
and sets `env_prefix=None`; the upstream CLI source constructs an environment
source to describe environment names, which calls `len(None)`. Confidantic
normalizes the prefix when building its own parser, but direct source
construction does not go through that normalization.

```python
from pydantic_settings import CliSettingsSource
from confidantic import BaseConfig


class Config(BaseConfig):
    value: int = 1


source = CliSettingsSource(Config, cli_parse_args=["--value", "7"])
config = Config(_cli_settings_source=source, _cli_parse_args=False)
assert config.value == 7
```

Expected: a supplied CLI source can be constructed using the model's defaults,
while the disabled environment source contributes no environment-name help.
Affected: custom parser/source construction with the default `env_prefix=None`
and environment-name help enabled. Passing `cli_show_env_vars=False` to the
source avoids the error. Setting an explicit string prefix also works, but
enables environment parsing and therefore changes settings behavior. The same
construction succeeds for an ordinary Pydantic `BaseSettings` subclass.

Regression coverage is in
`tests/_config/test_cli.py::test_supplied_cli_source_keeps_its_parser_and_values`:
the default-help case is a strict expected failure, and the disabled-help
workaround must pass.
