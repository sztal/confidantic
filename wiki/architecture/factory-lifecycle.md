# Factory lifecycle

Factory separates discovery of configuration fields from construction of runtime
objects. It reuses BaseConfig sources and validation between those stages.

```text
target class                 template instance
     |                              |
     +------ model_from() ----------+
                    |
       inspect annotations and defaults
                    |
     optional __recursive__ selection
                    |
       generated Factory model class
                    |
       settings sources + validation
                    |
           Factory model instance
                    |
            model_resolve()
                    |
   recursive values + resolved model types
                    |
        target constructor keyword call
                    |
              runtime object
```

Supplying constructor arguments with a target class constructs a template before
generation. The diagram's resolution stage always traverses supported nested
factories; `__recursive__` governs generation of fields from defaults, not traversal.

## Schema and generation

[factory](../api/_config/factory.md) owns generic target compatibility and strict/lax
schema behavior because Pydantic invokes those hooks while classes are being created.
It imports the [builder](../api/_config/_factory_build.md) only when generation needs it.
The builder resolves constructor annotations, applies template attributes, preserves
required fields, and optionally rewrites selected defaults as nested factory fields.

Copied-default wrappers isolate mutable templates while allowing settings merging.
Generated annotations and supported concrete factory defaults expose nested fields
to the [CLI adapter](../api/_config/_cli.md). The generated class retains only the
schema/constructor metadata and defaults; it does not retain the builder.

## Resolution

Public methods establish CLI suppression before entering the
[resolver](../api/_config/_factory_resolution.md). Value traversal and model-type
reconstruction use separate state. The active value path detects cycles; a per-call
type cache coordinates replacement models and recursive annotations. Repeated values
are reconstructed independently, even when generated types are shared.

A Factory forwards only constructor fields to its target. A containing BaseConfig
rebuilds models with factory annotations replaced by target types. Other settings
sources still participate when those models validate. Arbitrary objects pass through
without their attributes being traversed, and target return values are not revisited.

## Persistence boundary

Generated classes are not automatically registered as module attributes. Portable
Make serialization of a factory identifies the target and its canonical constructor
arguments. Python process-serialization tests cover dynamic models separately;
temporary builder/resolver state must never become part of their payloads.

See [factory concepts](../concepts/factories-and-templates.md),
[object templates](../examples/object-templates.md), and
[resolution tests](../../tests/_config/test_factory_resolution.py).
Return to [architecture](README.md).
