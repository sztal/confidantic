# Construct objects from trusted documents

Ordinary [configuration documents](../guide/files.md) contain values for a known
model. Directives let a document name Python objects and constructors. Use them
when concrete object selection is part of your application format. Core Confidantic
supports directives; the YAML example additionally needs the `yaml` extra.

!!! warning "Directives execute Python imports and calls"

    Use `Import`, `Call`, and `Make` only with trusted input. Type validation does
    not prevent imported modules or constructors from having side effects.

## Import, Call, and Make

| Annotation  | Operation                                                             |
| ----------- | --------------------------------------------------------------------- |
| `Import[T]` | Import an object and validate it as `T`                               |
| `Call[T]`   | Evaluate one call and validate its result as `T`                      |
| `Make[T]`   | Evaluate nested supported directives, then validate the result as `T` |

This complete example uses an importable standard-library target:

```pycon
>>> from fractions import Fraction
>>> from pydantic import TypeAdapter
>>> from confidantic.annotations import Call, Import, Make
>>> fraction_type = TypeAdapter(Import[type[Fraction]]).validate_python("fractions:Fraction")
>>> value = TypeAdapter(Call[Fraction]).validate_python(
...     {"@call": "fractions:Fraction", "@args": [1, 2]}
... )
>>> values = TypeAdapter(Make[list[Fraction]]).validate_python(
...     [{"@call": "fractions:Fraction", "@args": [1, 3]}]
... )
>>> print(fraction_type.__name__)
Fraction
>>> print(value)
1/2
>>> print(values[0])
1/3

```

`Call` leaves nested arguments untouched. `Make` visits mapping values, lists,
and tuples, but not mapping keys or call results. Ordinary nested strings and
callables remain data. At the top level, `Call` and `Make` also accept strings as
import-and-call requests. An `@call` mapping accepts positional `@args` and ordinary
keyword entries.

## Make directives

Run the following example and its continuations together in one Python script.

Pass `context={"make": True}` to `model_dump()` or `model_dump_json()` to add
a `Make` directive for each serialized `BaseConfig`:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
    retries: int = 3


config = AppConfig()
data = config.model_dump(context={"make": True})
# When run as a script: {"@call": "__main__:AppConfig", "retries": 3}
```

Nested `BaseConfig` instances receive their own directive; ordinary Pydantic
models do not. A `Factory` writes its target class's identifier, so loading
its directive calls the target constructor. Factory directives contain only
`factory_fields`, using canonical constructor keyword names even when
`by_alias=True` or `serialize_by_alias` is configured. Field serializers and
include/exclude filters still apply. Ambiguous serialized constructor keys and
serializer failures raise errors instead of producing unusable directives.
Identifiers must resolve to
importable objects; local and unregistered generated classes are not portable.
Use `serialize_as_any=True` when fields annotated with base classes must retain
subclass-only data.

Deserialize the result with the `Make` annotation:

```python
from confidantic.annotations import Make
from pydantic import BaseModel


class Container(BaseModel):
	config: Make[AppConfig]


config = Container.model_validate({"config": data}).config
```

This feature is intended for trusted serialized data: the directive controls an
import and invokes the selected class constructor.

For a concrete output check, append `print(type(config).__name__, config.retries)`
after the deserialization block. It prints `AppConfig 3`. Both the producer and
consumer are in the same script, so the `__main__` identifier can resolve.

## Formats and portability

YAML and TOML model loaders do not interpret a root `@call`. Parse the document,
then validate it through `Make`. Continuing with the preceding `AppConfig` and
`config`, after installing `confidantic[yaml]`:

```python
import yaml
from pydantic import TypeAdapter
from confidantic.annotations import Make


yaml_text = config.model_dump_yaml(context={"make": True})
loaded_yaml = TypeAdapter(Make[AppConfig]).validate_python(yaml.safe_load(yaml_text))
print(type(loaded_yaml).__name__, loaded_yaml.retries)
```

This also prints `AppConfig 3`. For transfer between programs, define targets in
an importable application module available to the receiver. Local classes and
unregistered generated configuration classes are not portable import identifiers.
Factory directives name their target constructor rather than their generated class.

Loading a directive does not retain the original directive for a later dump.
BaseConfig's explicit `make` context creates new directives. Excluding required
constructor inputs can make reconstruction fail, even if the filtered document
itself is valid JSON or YAML.

Pickle and cloudpickle serve different Python-object transfer needs. They are not
a stable interchange contract for private layouts or old payloads, and they do
not transfer context activation or temporary validation state.

For a nested subtype round trip, see the
[wiki portable-object guide](https://github.com/sztal/confidantic/blob/master/wiki/examples/advanced/portable-object-graphs.md).
