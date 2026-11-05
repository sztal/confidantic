# confidantic.\_config.\_nested

`_NestedModelUpdates` connects merged source input to BaseConfig's field validators.
It preserves a concrete model instance as a baseline when a higher-priority mapping
partially updates that field. The module is private and supplies no independent
settings API.

## Select, then apply

`scope()` installs a fresh baseline map in a ContextVar and restores the previous
token in `finally`. `prepare()` considers mapping-valued fields, skips discriminated
fields, and looks for initialization model instances before falling back to defaults.
An unpatched initialization instance is restored directly. A patched instance becomes
a baseline; model-valued default factories use a deferred sentinel.

The sentinel postpones factory evaluation until `apply()` receives ValidationInfo.
Previously validated fields are then available to data-aware default factories.
Annotation inspection recognizes model types through Annotated and unions, but
does not search container element types. Only a model-valued field is a baseline.

`_update_model()` gathers stored fields rather than serialized representations,
matches aliases, recursively patches nested models, merges extras, and validates
through the baseline's concrete class. Discriminated descendants select replacement
variants. Explicit-field metadata combines previous explicit fields with patched
fields. The baseline object itself is not assigned new fields.

## Constraints and preservation rules

The reconstruction pass does not forward outer strictness, extra policy, or
validation context; see [the tracked limitation](../../../BUGS.md). Disabling
partial updates avoids this path but also changes baseline and subtype retention.
Do not describe the path as an unvalidated dictionary update: nested validators
and settings can run again, and their exceptions propagate.

Preserve scope restoration for nested calls and exceptions, deferred evaluation,
alias handling, and discriminated replacement. Do not move baseline maps onto model
classes or capture them in generated callbacks. Observable behavior is exercised
through BaseConfig even though ownership is here.

Evidence: [source](../../../confidantic/_config/_nested.py) and
[nested tests](../../../tests/_config/test_nested.py).
See [nested configuration](../../concepts/nested-configuration.md),
[its guide](../../examples/nested-config.md), and [the index](README.md).
