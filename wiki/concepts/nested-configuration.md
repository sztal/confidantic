# Nested configuration

Nested fields can contain ordinary Pydantic models, other BaseConfig models,
mappings, or factories. Their annotations still control validation, but source
merging and partial updates determine which input reaches that validation.

## Mapping merge versus model baseline

Mappings are deep-merged across sources so a lower-priority mapping can supply
missing keys. Lists and other non-mapping values are replaced rather than concatenated.
With `nested_model_default_partial_update=True`, a mapping can also patch a concrete
model instance supplied as a default or lower-priority initializer input.

That model instance supplies both existing values and its concrete class. A field
annotated as a base model can therefore retain a subclass default and its additional
fields after a partial update. The reconstruction uses stored values, not a model
dump, and validates a new instance; field serializers do not define the baseline.

## Factories and variants

Ordinary default factories remain lazy. Their values are evaluated during field
validation, when previously validated data is available. At the source level they
block lower-priority values for the whole field. Generated copied-default wrappers
used by Factory are special: their templates can participate in source merging.

Discriminated fields select a replacement variant instead of patching a baseline
from another variant. This applies to nested descendants as well. An unchanged
initialization model can be retained directly when no higher-priority mapping patches it.

## Choosing the policy

Disable partial updates when the annotated model should be built from supplied
input without retaining a concrete baseline. This changes subtype and default-value
retention, not just performance. The separate baseline reconstruction currently
does not forward outer per-call strictness, extra policy, or validation context;
the confirmed limitation is tracked in [BUGS.md](../../BUGS.md).

Read [the nested guide](../examples/nested-config.md) for concrete subclass defaults,
[\_nested](../api/_config/_nested.md) for reconstruction, and
[the settings lifecycle](../architecture/settings-lifecycle.md) for scope ownership.
Return to [all concepts](README.md).
