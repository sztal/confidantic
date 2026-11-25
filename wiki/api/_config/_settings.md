# confidantic.\_config.\_settings

This module owns source assembly, class-default contributions, source provenance,
and the schema wrapper used by BaseConfig. `ClassDefaultsSource` is public through
the root package. Other classes and callbacks are implementation collaborators.

## Assemble one ordered chain

`_SettingsSources` belongs to one construction. It copies bound source options,
separates custom per-call options, and optionally discovers a dotenv file once.
Bare BaseConfig delegates to the upstream builder. For subclasses, `build()` visits
the supplied C3 MRO levels from concrete to parent.

For each level, `_sources_for_level` invokes the upstream source builder bound to
that class. `_CliSettings` resolves parser and environment policy. Only the concrete
level retains CLI sources. An exact built-in environment source is removed when
that level's prefix is None; custom subclasses are retained. Exact initializer
sources are replaced by the local adapter. Upstream default sources are replaced
by defaults declared at that class level. A terminal provenance observer completes
the flattened chain. BaseConfig then delegates the actual merge upstream.

This ordering means a child default precedes a parent's environment source. Sources
still execute even when higher-priority values have already filled every field.

## Defaults and barriers

`ClassDefaultsSource` selects directly declared annotated fields unless given an
explicit field collection. Required fields contribute nothing. Static defaults
are dumped through a TypeAdapter into source values using the field's first alias.
Ordinary default factories and discriminated defaults instead contribute a sentinel
that blocks lower-priority values without prematurely evaluating the default.

`_CopiedDefault` is the exception: it retains a generated factory template and
deep-copies it when called. Its copied values participate in ordinary source merging.
Keep this wrapper distinct from arbitrary default factories, including data-aware
factories that require previously validated fields.

`finalize_values()` removes untouched default contributions so Pydantic applies
actual defaults and keeps correct explicit-field metadata. It then prepares nested
model baselines when partial updates are enabled in the active scope.

## Provenance and initialization tracking

`_ProvenanceSource` contributes no values. It compares successive source states to
find the first source establishing each canonical field. It records both source
class and owning configuration class. Extras are considered for initialization
tracking but are not exposed as field provenance. Any bare callable source disables
automatic provenance for the chain because it lacks the required source state.

`track_customization()` marks entries that remain identical to those in the actual
initializer source supplied to the customization hook. Validated copies use that
information to distinguish carried values from newly sourced values. The wrapper
preserves method metadata and avoids wrapping itself repeatedly.

## Validation integration and errors

`wrap_settings_schema()` leaves definition references intact and attaches recursive
references to the wrapper. `validate_settings()` separates mapping input into field
values and source options, suppresses automatic CLI in notebook/resolution contexts,
and runs merged input through the remaining validation handler inside a fresh nested
scope. It attaches provenance after validation. Non-mapping input goes directly to
the handler.

The initializer adapter catches only the upstream unhashable-dictionary TypeError;
other source, validation, and dependency errors propagate. Preserve this narrow
fallback, per-call option handling, default laziness, exact-type normalization,
and cleanup of nested scopes when editing the module.

Evidence: [source](../../../src/confidantic/_config/_settings.py) and
[settings tests](../../../tests/_config/test_settings.py).
Read [source semantics](../../concepts/sources-and-inheritance.md),
[the lifecycle](../../architecture/settings-lifecycle.md), and
[custom sources](../../examples/advanced/custom-sources.md). Return to [the index](README.md).
