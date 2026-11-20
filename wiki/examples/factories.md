# Generate configuration from constructors

[factory.py](../../examples/factory.py) needs only core Confidantic. It defines a
Service dataclass with required `host` and default `port=8000`.

```console
uv run python examples/factory.py
```

## Generate, validate, resolve

Excerpt after the Service definition:

```python
ServiceConfig = Factory.model_from(Service)
assert ServiceConfig.model_fields["host"].is_required()
```

The script checks that omitting host raises ValidationError. With valid fields,
the next excerpt explicitly constructs the target:

```python
config = ServiceConfig(host="api.example.com", port=8080)
assert isinstance(config, Factory)
service = config.instance()
assert isinstance(service, Service)
assert service == Service("api.example.com", 8080)
print(service)
```

Generating ServiceConfig creates a configuration class. Instantiating it validates
settings. Calling instance builds the runtime Service from constructor fields.

## Capture template defaults

Later, the script creates a Service template at `template.example.com:9000` and
generates TemplateConfig from that instance. Overriding the generated port to 9001
leaves the template unchanged. `Factory.instance_from(Service, host=...)` demonstrates
the generation-and-instantiation shortcut; it still requires explicit resolution.

Expected output:

```text
Service(host='api.example.com', port=8080)
Service(host='worker.example.com', port=8000)
```

By default, constructor fields need resolvable annotations. Unannotated required
parameters can fail later at target construction. See
[annotation resolution](advanced/factory-annotations.md) for explicit namespaces
and permissive generation. Selected positional-only parameters are unsupported;
exclude them and supply them positionally at construction.

## Keep runtime inputs outside configuration

The final section of the same script excludes `host` from the schema:

```python
PortConfig = Factory.model_from(Service, __exclude__={"host"})
partial = PortConfig(port=9000)
assert partial.instance("runtime.example.com") == Service("runtime.example.com", 9000)
```

Creating `partial` needs no host; calling `partial.instance()` without one raises
`TypeError`. The excluded parameter is absent from the schema and CLI. Excluded
parameters with defaults use constructor defaults rather than template attributes.

The following supplemental alternatives reuse `Service` and `Factory` from the
script; they are not additional script excerpts:

```python
PortConfig = Factory.model_from(Service, __include__={"port"})
PortConfig = Factory.model_from(Service, __include__=lambda name: name == "port")
PortConfig = Factory.model_from(
    Service, __include__=lambda field_type, name: field_type is int
)
```

Use one selector only. Name sets and one-argument predicates filter before
annotation resolution; two-argument predicates inspect resolved annotations.
Unknown names are errors. Selection applies only to the root factory, not to
recursively generated dependencies. An incomplete nested factory needs its own
runtime inputs: construct it explicitly and pass the result to the outer factory.

## Choose raw overrides or validated updates

These assertions are also in the runnable script:

```python
assert partial.instance("runtime.example.com", port="9001").port == "9001"
assert partial.copy(port="9001").instance("runtime.example.com").port == 9001
assert isinstance(partial.model_resolve(), Factory)
```

Runtime arguments follow the constructor signature and override configured values
without additional field validation or source lookup. Missing inputs, duplicate
bindings, and unexpected arguments raise `TypeError` before dependencies are
constructed. Overridden dependencies are not constructed. Configuration remains
unchanged; use `copy()` first when values need validation and conversion.

For migration, replace `factory.model_resolve()` calls intended to construct the
root target with `factory.instance()`. Both Factory and BaseConfig now preserve
the root model in `model_resolve()` while constructing nested factories.
`instance_from()` still returns a configuration, and factory instances are not
callable. Keep outer `BaseConfig.model_resolve()` calls that prepare object graphs.

Continue with [object templates](object-templates.md). Read
[factory concepts](../concepts/factories-and-templates.md),
[Factory internals](../api/_config/factory.md), or [all guides](README.md).
