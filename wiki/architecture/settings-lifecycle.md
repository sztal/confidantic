# Settings lifecycle

BaseConfig assembles settings inside Pydantic's active validation schema. This lets
normal validation receive merged inputs while retaining the outer call's options.
The process has separate owners for source preparation, merging, baseline updates,
and provenance.

```text
constructor / model_validate / nested model input
                         |
              settings schema wrapper
                         |
          bind options and build MRO sources
                         |
 concrete: CLI -> init -> env -> dotenv -> secrets -> defaults
 parent:         init -> env -> dotenv -> secrets -> defaults
 ...remaining C3 MRO levels...
                         |
       upstream merge + provenance observer
                         |
      remove default barriers, prepare baselines
                         |
      Pydantic validation + nested field updates
                         |
           attach provenance to the result
```

The diagram shows ordinary enabled sources. Custom hooks can reorder a level,
environment input is opt-in, and BaseConfig itself is excluded from subclass MRO
levels. Non-mapping input follows Pydantic's handler directly.

## Source construction and merging

The [base adapter](../api/_config/base.md) binds arguments against the installed
upstream builder signature. [\_SettingsSources](../api/_config/_settings.md) resolves
custom per-call options and constructs each level's sources through upstream hooks.
It retains CLI only at the concrete level and replaces upstream defaults with
directly declared class defaults. The provenance observer supplies no settings data.

BaseSettings performs the merge over this flattened sequence. Nested mappings
combine, while other values obey priority. Class default-factory barriers prevent
lower levels from supplying a field before Pydantic evaluates its default. Generated
copied templates contribute mergeable values instead of ordinary factory barriers.

## Validation and state

A fresh [\_NestedModelUpdates](../api/_config/_nested.md) scope surrounds value
assembly and validation. Finalization removes untouched defaults and records model
baselines. Field validators apply partial updates, evaluating deferred data-aware
factories only when earlier validated fields are available. Pydantic then performs
normal field and model validation.

The scope token is reset on success or failure, including nested construction.
After validation, source-winner and initialization metadata are copied onto the
result. Source errors can occur even when earlier values already filled every field;
construction does not stop evaluating sources early.

Preserve recursive schema references on the wrapper, or nested recursive models
can bypass source assembly. Preserve subclass hook dispatch and active validation
options. The separate nested-baseline option limitation is tracked in
[BUGS.md](../../BUGS.md).

See [source semantics](../concepts/sources-and-inheritance.md),
[custom-source examples](../examples/advanced/custom-sources.md), and
[settings tests](../../tests/_config/test_settings.py). Return to [architecture](README.md).
