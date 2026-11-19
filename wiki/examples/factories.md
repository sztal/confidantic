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

Constructor fields need annotations. Positional-only annotated parameters are not
supported because resolution calls by keyword. Unannotated required parameters can
fail later at target construction. Apply configuration updates before resolution.

Continue with [object templates](object-templates.md). Read
[factory concepts](../concepts/factories-and-templates.md),
[Factory internals](../api/_config/factory.md), or [all guides](README.md).
