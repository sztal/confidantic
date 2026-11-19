# Choose between Confidantic, Pydantic, and Pydantic Settings

Confidantic builds on Pydantic and Pydantic Settings. It adds configuration
inheritance rules, provenance, validated updates, and a workflow for constructing
application objects from settings. Ordinary Pydantic fields, constraints,
validators, and serializers remain available.

| Abstraction                            | Main responsibility                                                                      | Typical fit                                            |
| -------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Pydantic `BaseModel`                   | Validate and serialize supplied data                                                     | Request bodies, records, and data-transfer models      |
| Pydantic Settings `BaseSettings`       | Assemble validated settings from configurable sources, including CLI input               | Applications needing standard settings loading         |
| Confidantic `BaseConfig` and `Factory` | Add inheritance-aware precedence, provenance, validated updates, and object construction | Layered application settings and configured components |

[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) already
provide nested models, dynamic model creation, optional freezing, validation, and
serialization. [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
already supplies environment, dotenv, secrets, custom sources, CLI support with
subcommands, and optional partial updates to nested default models. Confidantic
uses those capabilities as foundations.

## Inheritance determines source priority

Within one configuration class, enabled sources normally run in this order:
CLI, initializer, environment, dotenv, secrets, then defaults. Confidantic also
orders contributions by concrete-to-parent inheritance: a child default can
outrank a parent environment value. Each level retains its source policy.
Process environment loading is enabled with a string `env_prefix`, including
`""` for unprefixed names; `None` disables that source at that level.

This example supplies a parent environment value temporarily, restoring the
environment when the `with` block ends:

```pycon
>>> import os
>>> from unittest.mock import patch
>>> from confidantic import BaseConfig, ClassDefaultsSource
>>> class ParentConfig(BaseConfig, env_prefix="DOCS_PARENT_"):
...     retries: int = 3
>>> class ChildConfig(ParentConfig, env_prefix=None):
...     retries: int = 5
>>> with patch.dict(os.environ, {"DOCS_PARENT_RETRIES": "9"}):
...     assert ParentConfig().retries == 9
...     child = ChildConfig()
...     assert child.retries == 5
...     assert child.model_field_sources["retries"] == (ClassDefaultsSource, ChildConfig)

```

`model_field_sources` identifies the source class and configuration class that
established a top-level field. It does not track every nested key's origin.
Read [values and inheritance](../concepts/values-and-inheritance.md) and
[source provenance](../guide/sources.md#explain-a-values-origin) for the full rules.

## Updated copies validate inputs

Confidantic freezes field assignment by default and offers validated
`copy(**updates)`, `deepcopy(**updates)`, and explicit `mutate(**updates)`.
Pydantic's [model_copy](https://docs.pydantic.dev/latest/concepts/models/#model-copy)
accepts unchecked updates:

```pycon
>>> from pydantic import Field, ValidationError
>>> from confidantic import BaseConfig
>>> class RetryConfig(BaseConfig):
...     retries: int = Field(3, ge=0)
>>> original = RetryConfig()
>>> original.model_copy(update={"retries": "4"}).retries
'4'
>>> original.copy(retries="4").retries
4
>>> try:
...     original.copy(retries=-1)
... except ValidationError:
...     print("Negative retries rejected")
Negative retries rejected
>>> original.retries
3

```

Freezing is shallow: nested mutable values can still change. Updated copies
revalidate and can consult configured sources again. Copies without updates are
structural copies. Choose the appropriate operation using
[settings and updates](../guide/settings.md#frozen-configuration).

## Settings can construct application objects

`Factory.model_from(Target)` derives a configuration class from an annotated
constructor. A template instance can supply defaults; `__recursive__` can convert
matching concrete dependencies into nested factories and expose their CLI fields.
This avoids manually repeating constructor parameters as configuration fields.

Creating a factory instance validates settings. Calling `instance()` constructs
the target. Calling `model_resolve()` preserves the root configuration while
constructing nested factories. Include/exclude selectors let runtime inputs stay
outside the root configuration schema. Runtime `instance()` overrides receive no
additional field validation; use a validated copy when conversion or constraints
are needed.

Follow the [factory guide](../guide/factories.md) for examples, annotation policies,
and partial factories, then [recursive templates](../advanced/dynamic-template-clis.md)
for configurable dependencies. Pydantic provides dynamic schema machinery;
Confidantic supplies the constructor/template workflow and traversal policy.

## Choose what the application needs

Use `BaseModel` when data should not consult settings sources. Use `BaseSettings`
when its loading and CLI behavior already fits. Add Confidantic when its
inheritance rules, update semantics, or construction workflow reduce
application-specific configuration code.

Confidantic also provides [objects that own configuration](../recipes/configurable-objects.md),
[context-local active settings](../recipes/contexts.md),
[input annotations](../guide/input-parsing.md), [path helpers](../recipes/paths.md),
[logging configuration](../recipes/logging.md), and optional Rich
[display methods](../guide/descriptions-and-display.md). Shared configuration
mutation does not refresh resources or constructor-derived caches automatically.

Read [configuration and objects](../concepts/configuration-and-objects.md) to choose a
construction pattern and [nested settings](../guide/nested-settings.md) before
relying on concrete-default reconstruction.
