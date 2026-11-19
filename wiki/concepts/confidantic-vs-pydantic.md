# Confidantic, Pydantic, and Pydantic Settings

Confidantic builds on Pydantic and Pydantic Settings. Use it when configuration
inheritance and the construction of application objects are part of your design.
Its added value is the behavior connecting those tasks, while ordinary Pydantic
fields, constraints, validators, and serializers remain available.

## Choose the abstraction

| Abstraction                            | Main responsibility                                                                                    | Typical fit                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Pydantic `BaseModel`                   | Validate and serialize explicitly supplied data                                                        | Request bodies, records, and data-transfer models                  |
| Pydantic Settings `BaseSettings`       | Assemble validated settings from configurable sources, including CLI input                             | Applications needing standard settings loading                     |
| Confidantic `BaseConfig` and `Factory` | Add inheritance-aware source behavior, provenance, validated updates, and explicit object construction | Layered application configurations and configured component graphs |

[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) already
provide nested models, dynamic model creation, optional freezing, validation, and
serialization. [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
already supplies environment, dotenv, secrets, custom sources, and CLI support,
including subcommands and optional partial updates to nested default models.
Those capabilities are foundations used by Confidantic, not exclusive additions.

## Inheritance affects source priority

Within one class, enabled sources normally follow CLI, initializer, environment,
dotenv, secrets, then defaults. Confidantic additionally assembles sources by
concrete-to-parent MRO: a child's declared default can outrank a parent's
environment input. Each level retains its source policy. Process environment
loading is opt-in through a string `env_prefix`; `None` disables that source at
that level.

This complete supplemental example temporarily supplies one environment value:

```python
import os

from confidantic import BaseConfig, ClassDefaultsSource


class Parent(BaseConfig, env_prefix="WIKI_PARENT_"):
    retries: int = 3


class Child(Parent, env_prefix=None):
    retries: int = 5


previous = os.environ.get("WIKI_PARENT_RETRIES")
os.environ["WIKI_PARENT_RETRIES"] = "9"
try:
    assert Parent().retries == 9
    child = Child()
    assert child.retries == 5
    assert child.model_field_sources["retries"] == (ClassDefaultsSource, Child)
finally:
    if previous is None:
        del os.environ["WIKI_PARENT_RETRIES"]
    else:
        os.environ["WIKI_PARENT_RETRIES"] = previous
```

`model_field_sources` identifies the source class and configuration class that
established each top-level field; it is not per-key nested provenance. See
[sources and inheritance](sources-and-inheritance.md), the runnable
[environment guide](../examples/environment-and-dotenv.md), and
[source tests](../../tests/_config/test_settings.py).

## Updates validate deliberately

Confidantic freezes field assignment by default and offers validated
`copy(**updates)`, `deepcopy(**updates)`, and explicit `mutate(**updates)`.
Pydantic's [model_copy](https://docs.pydantic.dev/latest/concepts/models/#model-copy)
accepts unchecked updates. This complete supplemental example shows the practical
difference:

```python
from pydantic import Field, ValidationError

from confidantic import BaseConfig


class RetryConfig(BaseConfig):
    retries: int = Field(3, ge=0)


original = RetryConfig()
assert original.model_copy(update={"retries": "4"}).retries == "4"
assert original.copy(retries="4").retries == 4
try:
    original.copy(retries=-1)
except ValidationError:
    pass
else:
    raise AssertionError("Validated updates must reject negative retries")
assert original.retries == 3
```

Freezing is shallow: nested lists and arbitrary objects can remain mutable.
Updated copies revalidate and can consult configured sources again; they are not
guaranteed to be isolated dictionary replacements. Copies without updates are
structural copies. See [configuration models](configuration-models.md),
[the update guide](../examples/defining-config.md), and
[BaseConfig tests](../../tests/_config/test_base.py).

## Configuration can construct application objects

`Factory.model_from(Target)` derives a configuration class from an annotated
constructor. A template instance can supply defaults; `__recursive__` can turn
matching concrete dependencies into nested factories and expose their CLI fields.
This connects validated configuration to runtime construction without manually
repeating each constructor as a model.

Instantiating that generated class validates configuration. Calling `instance()`
constructs the target. Calling `model_resolve()` preserves the root configuration
and constructs nested factories. Root-only include/exclude selectors let runtime
inputs stay outside the configuration schema. Runtime `instance()` overrides
receive no additional field validation; use validated copies when conversion or
constraints are needed.

Follow [factories](../examples/factories.md),
[object templates](../examples/object-templates.md), and
[annotation resolution](../examples/advanced/factory-annotations.md).
[Factory tests](../../tests/_config/test_factory.py) and
[resolution tests](../../tests/_config/test_factory_resolution.py) cover the
construction boundary. Pydantic's dynamic models provide schema machinery;
Confidantic supplies this constructor/template workflow and traversal policy.

## Runtime conveniences and boundaries

[Configurable objects](configured-objects.md) explicitly pair durable inputs with
runtime resources; [contexts](contexts.md) provide context-local active settings.
[Input annotations](input-annotations.md), [path helpers](../examples/paths.md),
[logging configuration](../examples/logging.md), and Rich
[configuration display](../examples/defining-config.md#control-display-rows) support
common application tasks. Shared configuration mutation does not refresh resources
or constructor-derived caches automatically.

Choose `BaseModel` when data should not consult settings sources. Use
`BaseSettings` when its loading and CLI behavior already fits. Add Confidantic
when its precedence rules, update semantics, or object-construction workflow
reduce application-specific configuration code. Read
[nested configuration](nested-configuration.md) before relying on concrete-default
reconstruction and consult [BUGS.md](../../BUGS.md) for tracked source defects.

The two snippets above supplement the linked runnable guides and are not collected
by default pytest. Return to [concepts](README.md) or the [handbook](../README.md).
