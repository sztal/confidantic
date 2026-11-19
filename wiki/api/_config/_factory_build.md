# confidantic.\_config.\_factory_build

`_FactoryModelBuilder` turns one target constructor and optional template into a
concrete Factory class. Each `model_from` call creates a builder; nested generation
creates independent builders. Generated classes retain fields and copied templates,
not builder instances.

## Constructor inspection

`build()` combines module namespaces along the target's MRO with constructor globals
before evaluating type hints with extras retained. This supports inherited constructors
whose annotations name types in their defining module. Signature order determines
field order. Unannotated parameters and variadic arguments are omitted; annotated
positional-only parameters raise TypeError because resolution passes keywords.

Root-only `__include__` / `__exclude__` selectors filter names before annotation
resolution or inspect resolved annotations before recursive conversion. Name sets
are snapshotted; predicate arity is checked once. Selection policy is retained on
generated models for schema rebuilds and target conversions.

A matching attribute on the template replaces the constructor default. A missing
attribute leaves the constructor default, or keeps the field required. Fields are
created on the selected Factory base through Pydantic `create_model`, then
`factory_target` and ordered `factory_fields` are assigned to the new class.

## Recursive selection and copied defaults

`matches_selector` skips existing factories. Types, typing forms, and NewType use
strict TypeAdapter matching, excluding None; other callables receive the concrete
default as a predicate. Adapter configuration is retried only for the model-owned
configuration error. Predicate and annotation-construction errors propagate.

A selected default recursively generates a factory. `replace_annotation` replaces
matching union branches and preserves Annotated metadata and unrelated alternatives.
Selection examines a whole default, not each element of a container. Required fields
with no concrete value cannot be selected.

Mutable collections, factory instances, and unhashable defaults become
`Field(default_factory=_CopiedDefault(...))`. That wrapper deep-copies for each
configuration while still supplying mergeable source templates. Other hashable
defaults follow Pydantic's ordinary behavior. Explicit inputs use normal validation.

## When changing this module

Preserve annotation extras, parameter order, requiredness, and independence of copied
mutable defaults. Do not instantiate target types merely to discover missing defaults.
Generated classes are not registered on their declared module. Changes to copied
defaults need settings-merge and provenance tests as well as factory tests.

Evidence: [source](../../../confidantic/_config/_factory_build.py) and
[builder tests](../../../tests/_config/test_factory_build.py).
See [factories and templates](../../concepts/factories-and-templates.md),
[object templates](../../examples/object-templates.md), and [the index](README.md).
