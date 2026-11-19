# Build application objects from configuration

Suppose your application already has a class with an annotated constructor. A
[Factory][confidantic.Factory] derives a configuration model from those parameters,
so you can validate inputs before constructing the object.
For the library boundaries, see
[Confidantic and Pydantic](../getting-started/confidantic-vs-pydantic.md).
The runnable [factory.py](https://github.com/sztal/confidantic/blob/master/examples/factory.py)
demonstrates generation, templates, partial configuration, and runtime overrides.

## Generate, validate, then construct

This complete example uses a dataclass, whose generated constructor accepts
`host` and `port`:

```python
from dataclasses import dataclass

from confidantic import Factory


@dataclass
class Service:
    host: str
    port: int = 8000


ServiceConfig = Factory.model_from(Service)
config = ServiceConfig(host="api.example.com", port=8080)
service = config.instance()
print(service)
```

```text
Service(host='api.example.com', port=8080)
```

There are three separate steps:

1. `model_from(Service)` creates a **configuration class**. It does not construct
    a `Service` when no constructor arguments are supplied.
1. `ServiceConfig(...)` creates a **validated configuration instance**. `host` is
    required and `port` defaults to `8000`.
1. `instance()` calls the target constructor and returns the **application object**.

Supplying an invalid port fails during configuration validation. Construction can
still fail later if the target constructor raises an application-specific error.
The generated configuration uses the same settings behavior as `BaseConfig`.

With default strict generation (`__strict__=True`), annotated positional-or-keyword
and keyword-only parameters become fields.
Unannotated and variadic parameters are omitted; annotated positional-only
parameters are rejected. An omitted required argument can therefore fail when
the target is finally constructed. Annotate the constructor inputs you want to
configure, or use the annotation policies below.

## Control annotation resolution

Factory generation resolves constructor annotations at runtime. A type imported
only inside `if TYPE_CHECKING:` may therefore be unavailable even when calling
the constructor directly works. Supply missing names with `__types_namespace__`:

```python
from pathlib import Path

from confidantic import Factory


class Exporter:
    def __init__(self, destination: "OutputPath", label=None):
        self.destination = destination
        self.label = label


ExporterConfig = Factory.model_from(
    Exporter, __types_namespace__={"OutputPath": Path}
)
exporter = ExporterConfig(destination="output").instance()
assert exporter.destination == Path("output")
```

Explicit names take precedence over automatic lookup in the constructor's globals
and its target's inheritance hierarchy. Other names still use automatic lookup.
The mapping is shallow-copied without modifying the target module. It resolves
symbolic names; it does not replace type objects already stored in annotations.

Alternatively, opt into permissive generation with `__strict__=False`:

```python
config = Factory.instance_from(
    Exporter, __strict__=False, destination="output", label="daily"
)
exporter = config.instance()
assert exporter.destination == "output"
assert exporter.label == "daily"
```

| Constructor parameter                      | `__strict__=True` (default) | `__strict__=False` |
| ------------------------------------------ | --------------------------- | ------------------ |
| Resolvable annotation                      | Use its type                | Use its type       |
| Unresolved annotation name                 | Raise `NameError`           | Use `Any`          |
| No annotation                              | Omit parameter              | Include as `Any`   |
| Malformed annotation or unsupported schema | Raise                       | Raise              |

Fallback applies to the entire field: unresolved `list[Missing]` becomes `Any`,
not `list[Any]`. Such fields retain defaults and requiredness, but perform no
type validation or conversion. Valid annotations on other fields still apply.
This `__strict__` option controls annotation resolution, independently of
Pydantic's validation strictness. Permissive fallback emits no warning.

Both options are available on `model_from()` and `instance_from()` and can be
combined. They are generation arguments, not constructor arguments or field
inputs. `model_from(..., __recursive__=...)` passes them to nested generation;
matching defaults can still become nested factories even when their original
annotation falls back to `Any`. Return annotations and variadic parameters are
ignored. Positional-only parameters that would become fields are rejected.

Generated models retain their own policy for schema rebuilds, subclasses, and
validation-time conversion of target classes or instances. Later changes to the
supplied namespace mapping do not change that policy. New explicit `model_from()`
calls use their supplied options or the defaults above; plain `Factory[Target]`
annotations likewise use default strict resolution. Use the generated model as
the field type when its custom policy is needed.

## Use an object as a template

Continuing with the `Service` class above:

```python
template = Service("template.example.com", 9000)
TemplateConfig = Factory.model_from(template)
config = TemplateConfig(port=9001)
print(config.instance())
print(template)
```

```text
Service(host='template.example.com', port=9001)
Service(host='template.example.com', port=9000)
```

The template supplies concrete defaults through its matching attributes. Overrides
are applied to the configuration; resolving it constructs another service.
You can also pass constructor arguments to `model_from(Service, ...)` to first
construct a template.

`Factory.instance_from(Service, host="worker.example.com")` combines class generation
and configuration instantiation. It still returns a factory configuration; call
`instance()` to obtain the service.

## Compose dependencies

A configuration can contain generated factory fields. Calling `model_resolve()`
on an outer `BaseConfig` resolves supported nested factory values and returns a
validated model whose corresponding annotations describe the resolved targets.
Apply configuration updates before resolution.

Resolution visits supported model and container values, not arbitrary object
attributes. Repeated occurrences construct separately and traversed cycles fail.
Automatic CLI parsing is suppressed during target construction to avoid reading
the command line again; other settings sources remain active.

When a template already contains concrete dependency objects,
[`__recursive__` generation](../advanced/dynamic-template-clis.md) can expose those
dependencies as nested configuration fields. It is a generation option, not a
switch controlling whether resolution traverses nested factories.

Read [configuration and objects](../concepts/configuration-and-objects.md) for a
comparison with `Configurable`, or [the factory lifecycle](../architecture/factory-lifecycle.md)
for the flow through the package.

## Partial factories and runtime inputs

Select the parameters that belong in configuration using `__include__` or
`__exclude__`. The other parameters come from `instance()` arguments or constructor
defaults. For example, using the `Service` above:

```python
PortConfig = Factory.model_from(Service, __exclude__={"host"})
config = PortConfig(port=9000)
service = config.instance("runtime.example.com")
assert service == Service("runtime.example.com", 9000)
```

`host` is absent from the schema and CLI, so creating the configuration does not
require it. Calling `config.instance()` without `host` raises `TypeError`. An
excluded parameter uses its constructor default rather than a template attribute.

Both selectors accept sets or frozensets of names, predicates of a field name,
or predicates of `(resolved annotation, field name)`:

```python
PortConfig = Factory.model_from(Service, __include__={"port"})
PortConfig = Factory.model_from(Service, __include__=lambda name: name == "port")
PortConfig = Factory.model_from(
    Service, __include__=lambda field_type, name: field_type is int
)
```

Do not supply both selectors. Unknown names are errors. Empty inclusion generates
no constructor fields; empty exclusion retains all eligible fields. Predicates
must accept unambiguously one or two positional arguments, without variadics;
exceptions propagate. Name selectors run before annotation resolution, so they can
exclude a field with an unavailable type. Typed predicates see constructor
annotations before `__recursive__` replaces them with factory annotations and use
the existing `__strict__` annotation policy. Selection does not change annotation
eligibility or propagate to recursively generated factories.

Selected positional-only fields remain unsupported; exclude them and provide them
positionally to `instance()`. A constructor field named `instance` must also be
excluded so it cannot hide the construction method. Supply it with
`config.instance(instance=value)`. Excluding inherited model fields is rejected.

The `instance_from` shortcut accepts the same selectors:

```python
config = Factory.instance_from(Service, __include__={"port"}, port=9000)
assert config.instance(host="runtime.example.com").port == 9000
```

## Runtime overrides and validation

Runtime arguments use the original constructor's positional and keyword rules and
override configured values. They apply only to the root target. Duplicate runtime
bindings, unexpected keywords, and missing required inputs raise `TypeError` before
that target's dependencies are constructed. An overridden dependency is not built.
The original configuration is unchanged.

Runtime values receive no additional configuration-field validation or settings
lookup. Ordinary Python constructor annotations do not validate values:

```python
config = Factory.instance_from(Service, host="localhost")
assert config.instance(port="9000").port == "9000"
assert config.copy(port="9000").instance().port == 9000
assert config.port == 8000
```

Nested factories, models, and containers still undergo the normal recursive
resolution described above. Omitted constructor defaults are not newly traversed.
An incomplete nested factory raises `TypeError` during outer resolution; supply its
runtime inputs explicitly and pass the constructed object to the outer factory.

Ordinary dumps can be loaded through the known partial configuration class. Make
dumps retain the existing target-constructor directive format: an incomplete
partial factory's directive cannot execute until its missing arguments are added.
Factory instances remain non-callable, so `Make[Factory[T]]` and `Call[Factory[T]]`
can accept existing configurations without constructing their targets.

## Migrating construction calls

Replace target construction via `factory.model_resolve()` with `factory.instance()`.
`instance_from()` still returns a configuration. `model_resolve()` now has the same
meaning on both `Factory` and `BaseConfig`: return a model copy with nested factories
constructed, preserving the root model. It may still construct nested dependencies.

```python
config = Factory.instance_from(Service, host="localhost")
prepared = config.model_resolve(name="PreparedService")
assert isinstance(prepared, Factory)
assert prepared.instance() == config.instance()
assert not callable(config)
```

Keep `app_config.model_resolve()` calls that resolve factories inside an outer
configuration. No callable alias or compatibility construction override is retained.
