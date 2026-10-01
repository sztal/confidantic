# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

## Attribute-docstring inspection can fail during class reconstruction

A class defined in a module unavailable to a worker can fail cloudpickle
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
This defect remains unresolved in the dependency.

## Strict Factory validation accepts factories for unrelated targets

In `Factory.__get_pydantic_core_schema__`, the strict union's fallback accepts
any `Factory` instance without checking its target. On Python 3.13 with
Pydantic 2.13.4 and Pydantic Settings 2.15.0:

```python
from pydantic import TypeAdapter
from confidantic import Factory


class Expected:
    def __init__(self, value: int = 1) -> None:
        self.value = value


class Unrelated:
    pass


adapter = TypeAdapter(Factory[Expected])
wrong = Factory.instance_from(Unrelated)
assert adapter.validate_python(wrong, strict=True) is wrong
# The same validation with strict=False raises ValidationError.
```

Affected: typed factory fields and adapters using strict validation. Expected:
strict validation should reject incompatible target types at least as reliably
as lax validation, while retaining compatible factory instances.

## Recursive selectors call typing aliases instead of matching their types

`_matches_factory_selector` tests `callable(selector)` before recognizing
parameterized typing forms. `typing.Optional[T]` and `Annotated[T, ...]` are
callable, unlike a `T | None` union, and enter the predicate branch.

```python
from typing import Optional
from confidantic import Factory


class Child:
    def __init__(self, value: int = 1) -> None:
        self.value = value


class Parent:
    def __init__(self, child: Child = Child()) -> None:
        self.child = child


Factory.model_from(Parent, __recursive__=Optional[Child])
# TypeError: Cannot instantiate typing.Union
```

Affected: recursive model generation with callable type hints. With
`Annotated[Child, "tag"]`, the selector instead calls `Child(default)` and can
select unrelated defaults and run constructor side effects. Expected: type
hints use strict type matching without invoking their constructors. Concrete
types, `Child | None`, and explicit predicates work in the reproduction.

## Factory resolution cannot handle self-referential model annotations

`_resolved_annotation` and `_resolved_model_type` recurse through model
annotations without memoizing model types. The value graph need not contain a
cycle:

```python
from pydantic import BaseModel
from confidantic import BaseConfig, Factory


class Child:
    pass


class Node(BaseModel):
    child: "Node | None" = None


class Config(BaseConfig):
    node: Node = Node()
    factory: Factory[Child] = Factory.model_from(Child)


Config().model_resolve()
# RecursionError: maximum recursion depth exceeded
```

Affected: `BaseConfig.model_resolve()` and factory constructor inputs containing
self-referential or mutually recursive Pydantic model types. Expected: finite,
acyclic values resolve successfully; genuine value cycles still raise the
explicit cycle `ValueError`. A recursive annotation alone is not a value cycle.

## Settings reconstruction loses per-call validation options

YAML/TOML helpers forward validation options to `model_validate`, but the
settings constructor re-enters validation without preserving per-call `strict`,
`extra`, or field-validation `context`. Confirmed with Pydantic 2.13.4 and
Pydantic Settings 2.15.0; plain `BaseSettings` also reproduces the strictness
failure.

```python
from pydantic import ValidationInfo, field_validator
from confidantic import BaseConfig


class Config(BaseConfig):
    count: int = 1

    @field_validator("count")
    @classmethod
    def offset(cls, value: int, info: ValidationInfo) -> int:
        return value + (info.context or {}).get("offset", 0)


assert Config.model_validate_toml('count = "2"', strict=True).count == 2
assert Config.model_validate_toml("count = 2", context={"offset": 10}).count == 2
Config.model_validate_toml("count = 2\nunknown = 3", extra="ignore")
# ValidationError: extra inputs are not permitted
```

Affected: mapping construction through `model_validate` and the YAML/TOML
wrappers. Expected: strict mode rejects the numeric string, field validators
receive the supplied context, and the explicit extra policy overrides the
model policy. Class-level `strict` and `extra` settings remain effective.

## Validated copying can misreport values supplied by settings sources

`_copy_with_updates` reconstructs the model using active settings sources, then
overwrites the resulting provenance with old coordinates and marks requested
updates as initialization input regardless of which source won.

```python
from confidantic import BaseConfig


class Config(BaseConfig, cli_parse_args=["--value", "9"]):
    value: int = 1
    other: int = 0


original = Config(_cli_parse_args=False)
copied = original.copy(other=2)
assert copied.value == 9
assert copied.model_field_sources["value"][0].__name__ == "ClassDefaultsSource"
assert "value" not in copied.model_fields_set
updated = original.copy(value=2)
assert updated.value == 9
assert updated.model_field_sources["value"][0].__name__ == "InitSettingsSource"
```

Affected: `copy`, `deepcopy`, `mutate`, and configurable-object updates when CLI
or customized sources override reconstruction inputs. Expected: provenance and
explicit-field metadata describe the values actually installed, including
`CliSettingsSource` for `value` in both results above.

## Validated extra updates are omitted from explicit-field metadata

`_copy_with_updates` only adds declared field names to `model_fields_set`, even
when it successfully validates and installs new extra values.

```python
from confidantic import BaseConfig


class Config(BaseConfig, extra="allow"):
    pass


assert Config(label="new").model_fields_set == {"label"}
copied = Config().copy(label="new")
assert copied.model_extra == {"label": "new"}
assert copied.model_fields_set == set()
```

Affected: `copy`, `deepcopy`, and `mutate` with newly supplied extras. Expected:
explicitly updated extras participate in `model_fields_set`, consistent with
ordinary validated construction. Existing extras retain their previous
metadata, so this is specifically visible when an update introduces a new key.

## Factory Make serialization forwards fields the target does not accept

`Factory.model_resolve` forwards only `factory_fields`, but the inherited Make
serializer emits all serialized fields as target constructor arguments.

```python
from typing import Any
from pydantic import TypeAdapter
from confidantic import Factory
from confidantic.annotations import Make


class Target:
    def __init__(self, value: int = 1) -> None:
        self.value = value


Generated = Factory.model_from(Target)


class Extended(Generated):
    label: str = "metadata"


config = Extended()
assert config.model_resolve().value == 1
TypeAdapter(Make[Any]).validate_python(config.model_dump(context={"make": True}))
# TypeError: Target.__init__() got an unexpected keyword argument 'label'
```

Affected: factory directive dumps with subclass-only fields, allowed extras, or
computed fields that the target does not accept. Expected: target directives
use constructor inputs consistent with `factory_fields`, or explicitly reject
unsupported serialization before producing an unusable directive. Excluding
non-constructor fields manually is a workaround; alias output also needs to
match the target's constructor keyword names.
