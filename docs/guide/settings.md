# Define and update settings

A configuration class describes the values your application needs. A configuration
instance holds those values after validation. Start with
[BaseConfig][confidantic.BaseConfig] and ordinary Python type annotations:

```python
from confidantic import BaseConfig
from pydantic import Field


class AppConfig(BaseConfig):
    name: str
    retries: int = Field(default=3, ge=0)


config = AppConfig(name="orders", retries=5)
print(config.model_dump())
```

```text
{'name': 'orders', 'retries': 5}
```

`name` has no default, so it is required. `retries` defaults to `3`, and `ge=0`
requires a nonnegative value. Leaving out `name` or supplying `retries=-1` raises
Pydantic's `ValidationError`. Defaults are validated too.

## Choose model options

Use [ConfigModelDict][confidantic.ConfigModelDict] for settings behavior. For
example, add `model_config = ConfigModelDict(env_prefix="APP_")` to a class to
read environment variables. See [sources](sources.md) and the
[options reference](../reference/options.md) for complete examples and defaults.

Ordinary Pydantic constraints, aliases, validators, and serialization are available.
Use [BaseModel][pydantic.BaseModel] for data that should not consult settings sources;
use `BaseConfig` for application settings. Source values are assembled before your
model validators run, so those validators see merged inputs.
See [Confidantic versus Pydantic](../getting-started/confidantic-vs-pydantic.md) for a
comparison with both `BaseModel` and Pydantic Settings `BaseSettings`.

## Frozen configuration

`BaseConfig` instances are frozen by default, so model fields cannot be
reassigned after validation. Create a modified copy with `copy`; supplied
updates are validated as normal model input:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
	retries: int = 3


config = AppConfig()
updated = config.copy(retries=5)
```

`copy()` is shallow and `deepcopy()` recursively copies field values. Both
methods accept validated keyword updates. The standard-library `copy.copy()`
and `copy.deepcopy()` functions are also supported. With keyword updates, all
current fields and extras are validated again through settings construction;
validators can change untouched fields, CLI input can override updates, and
private attributes are initialized afresh. Deep copying happens before the
updates are applied, so supplied update objects are not themselves deep-copied.
Without updates, both methods preserve private state with the requested copy
depth. `mutate()` retains existing private state.

Use `mutate()` to apply validated updates to the same instance, including a
frozen configuration:

```python
config.mutate(retries=5)
```

Take care when mutating a frozen configuration: changing its fields may
invalidate its hash. Do not continue to use a mutated configuration as a
dictionary key or set member.

Pydantic's frozen behavior is shallow: mutable values stored in fields are not
recursively frozen. A subclass that intentionally requires field reassignment
can opt out:

```python
from confidantic import BaseConfig, ConfigModelDict


class MutableAppConfig(BaseConfig):
	model_config = ConfigModelDict(frozen=False)

	retries: int = 3
```

Pydantic's `model_copy(update=...)` does not validate updates. Choose Confidantic's
`copy(**updates)` when the new values need the same validation as initial inputs.

Here is a small executable example of an unchanged original:

```pycon
>>> from confidantic import BaseConfig
>>> class RetryConfig(BaseConfig):
...     retries: int = 3
>>> original = RetryConfig()
>>> updated = original.copy(retries=5)
>>> original.retries, updated.retries
(3, 5)

```

For mappings, nested models, and collection fields, read
[nested settings](nested-settings.md) before choosing a copy depth. To explain
where a value came from, continue with [sources](sources.md).
