# Factories and templates

Use Factory when a component already has an annotated constructor and should gain
validated configuration without manually repeating that constructor as a model.
The generated model uses ordinary BaseConfig source behavior.

## Four distinct values

| Value                   | Role                                                    |
| ----------------------- | ------------------------------------------------------- |
| Target class            | Defines annotated constructor parameters                |
| Template instance       | Supplies concrete defaults through matching attributes  |
| Generated Factory class | Describes configuration fields and constructor metadata |
| Factory instance        | Holds validated inputs, ready for explicit resolution   |

`Factory.model_from(Target)` returns a class without constructing Target when no
constructor arguments are supplied. Passing arguments first constructs a template.
Passing an existing instance uses it directly as the source of defaults. Required
parameters stay required unless a template supplies their values.

By default, annotated positional-or-keyword and keyword-only parameters become
fields; unannotated and variadic parameters are omitted. `__types_namespace__`
supplies names needed to resolve annotations. `__strict__=False` includes
unannotated parameters and falls back to `Any` for fields with unresolved names,
retaining defaults and requiredness. This policy is separate from validation
strictness; malformed annotations and unsupported schemas still fail.

Selected positional-only parameters are rejected. An omitted required parameter
can fail later when the target is called. `instance_from` is a shortcut for
generation followed by configuration instantiation; its keywords, apart from
generation options, are configuration inputs. See the
[annotation guide](../examples/advanced/factory-annotations.md).

## Partial configuration

Root-only `__include__` and `__exclude__` selectors choose constructor fields by
name sets or predicates. Use one selector, and supply missing required inputs at
`instance()` time. Excluded fields do not appear in the schema or CLI; their
defaults come from the constructor rather than a captured template. Selection
does not propagate to recursively generated factories. See
[partial factory examples](../examples/factories.md#keep-runtime-inputs-outside-configuration).

## Recursive templates and explicit resolution

`__recursive__` selects concrete defaults for conversion to nested factory fields.
Types and type hints use strict matching; predicates inspect each whole default.
It does not search individual collection elements or invent values for required
fields. Generated nested annotations expose dependency fields to validation and CLI.

`model_resolve()` always resolves supported nested factory values, regardless of
whether generation used `__recursive__`. Both Factory and BaseConfig preserve
their root model; when factories are found, resolution produces a validated model
with resolved target annotations. `Factory.instance()` constructs the target.
Repeated factory occurrences construct separately, cyclic traversed values fail,
and arbitrary object attributes are not traversed.

Use `copy(...).instance()` for validated updates, or `instance(*args, **kwargs)`
for raw runtime overrides. Only constructor fields and explicit runtime inputs
are passed to targets.
Mutable/copied defaults receive independent values, but this is not universal
deep-copy semantics for arbitrary objects. Generated classes are not automatically
importable; portable Make dumps of factories identify their targets instead.

Read [basic factories](../examples/factories.md),
[object templates](../examples/object-templates.md), and
[Factory internals](../api/_config/factory.md). Return to [concepts](README.md).
