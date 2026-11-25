# Reconstruct portable object graphs

Use Make when a trusted document should choose concrete constructors for nested
values. [directive_annotations.py](../../../examples/directive_annotations.py)
needs core Confidantic; [serialization.py](../../../examples/serialization.py)
also needs `rich` for its display call.

```console
uv run python examples/directive_annotations.py
uv run python examples/serialization.py
```

## Record and restore concrete types

The directive script defines ServiceConfig, HttpServiceConfig, and an application
whose service field is `Make[ServiceConfig]`. This excerpt uses those definitions:

```python
application = ApplicationConfig.model_validate(
    {
        "service": {
            "@call": "__main__:HttpServiceConfig",
            "name": "api",
            "url": "https://api.example.test",
        }
    }
)
serialized = application.model_dump(context={"make": True}, serialize_as_any=True)
restored = ConfigDocument.model_validate({"application": serialized}).application
```

Assertions confirm the ApplicationConfig and HttpServiceConfig types and equal
serialized values. The script prints `HttpServiceConfig` for the restored service.
The URL is data; the example makes no network request.

## Portability conditions

`__main__` identifiers resolve inside these self-contained scripts. For transfer to
another program, define targets in an importable application module available to
the receiver. Local classes and unregistered dynamic model names are not portable
import identifiers. Factory Make dumps identify target constructors instead of
generated configuration classes.

Make evaluates mapping values, lists, and tuples, but leaves mapping keys and call
results unvisited. Ordinary nested strings remain data. Dumping a resolved value
does not automatically recover its original directive; BaseConfig's explicit make
context produces new constructor directives.

For YAML/TOML containing directives, parse the document and validate the parsed
value through Make. Plain model format loaders do not evaluate a root directive.
Alternatively, a `Make[FromYaml[ServiceConfig]]` field reads a YAML path and
evaluates its directives during validation; JSON and TOML have corresponding file
annotations. The [serialization guide](../serialization.md#load-files-inside-nested-configuration)
includes a runnable nested example.
Constructor imports and calls execute code, so this recipe assumes trusted documents.

Read [serialization concepts](../../concepts/serialization.md),
[directive implementation](../../api/utils.md), and [advanced guides](README.md).
