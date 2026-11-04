# Build application objects from configuration

Suppose your application already has a class with an annotated constructor. A
[Factory][confidantic.Factory] derives a configuration model from those parameters,
so you can validate inputs before constructing the object.

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
service = config.model_resolve()
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
1. `model_resolve()` calls the target constructor and returns the **application object**.

Supplying an invalid port fails during configuration validation. Construction can
still fail later if the target constructor raises an application-specific error.
The generated configuration uses the same settings behavior as `BaseConfig`.

Annotated positional-or-keyword and keyword-only parameters become fields.
Unannotated and variadic parameters are omitted; annotated positional-only
parameters are rejected. An omitted required argument can therefore fail when
the target is finally constructed. Annotate the constructor inputs you want to
configure.

## Use an object as a template

Continuing with the `Service` class above:

```python
template = Service("template.example.com", 9000)
TemplateConfig = Factory.model_from(template)
config = TemplateConfig(port=9001)
print(config.model_resolve())
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
`model_resolve()` to obtain the service.

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
