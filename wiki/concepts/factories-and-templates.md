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

Annotated positional-or-keyword and keyword-only parameters become fields.
Unannotated and variadic parameters are omitted; annotated positional-only parameters
are rejected. An omitted required constructor parameter can therefore fail later
when the target is called. `instance_from` is a shortcut for generation followed by
configuration instantiation; its keywords are configuration inputs.

## Recursive templates and explicit resolution

`__recursive__` selects concrete defaults for conversion to nested factory fields.
Types and type hints use strict matching; predicates inspect each whole default.
It does not search individual collection elements or invent values for required
fields. Generated nested annotations expose dependency fields to validation and CLI.

`model_resolve()` always resolves supported nested factory values, regardless of
whether generation used `__recursive__`. A Factory produces its target; a BaseConfig
containing factories produces a validated model with resolved target annotations.
Repeated factory occurrences construct separately, cyclic traversed values fail,
and arbitrary object attributes are not traversed.

Apply updates before resolution. Only constructor fields are passed to targets.
Mutable/copied defaults receive independent values, but this is not universal
deep-copy semantics for arbitrary objects. Generated classes are not automatically
importable; portable Make dumps of factories identify their targets instead.

Read [basic factories](../examples/factories.md),
[object templates](../examples/object-templates.md), and
[Factory internals](../api/_config/factory.md). Return to [concepts](README.md).
