# confidantic.\_config.base

`BaseConfig` is the public settings model and adapter for the private collaborators.
Pydantic owns fields, schemas, validation, and serialization; Pydantic Settings
supplies source construction and merging. This module places Confidantic's policies
at their integration points rather than implementing another validation engine.

## Schema and subclass hooks

`__init__` uses BaseModel's initialization path. `__get_pydantic_core_schema__`
calls `wrap_settings_schema`, which routes mapping input through the overridable
`_validate_settings` class hook. That hook delegates to
[`_settings`](_settings.md), keeping source assembly inside the active validation
chain and preserving outer strictness, extra policy, and validation context.

`__pydantic_init_subclass__` wraps source customization to track unchanged
initializer input and expands active `@attrs` sections. It preserves class/static
method descriptor behavior. Optional docstring parsing is loaded only when an
active generation request requires it.

`_settings_init_sources` binds against the installed BaseSettings signature,
collects concrete-to-parent classes excluding BaseConfig, and delegates source
assembly. `_settings_build_values` uses the upstream merge before finalization.
The field-level before-validator applies the active nested-model baseline.
These hooks preserve subclass customization and upstream options.

## Defaults and updates

Defaults include frozen fields, validated defaults, disabled process environment,
`__` nesting, ignored empty environment values, and opt-in dotenv/CLI parsing.
Private instance metadata records source winners and carried initialization fields.
`model_field_sources` exposes a read-only view with canonical field names.

Structural `copy()` and `deepcopy()` without updates use Pydantic's copy protocols.
Updates pass through `_copy_with_updates`: resolve aliases, collect stored fields
and extras without dumping them, validate the combined mapping, then reconcile
provenance and explicit-field metadata. Sources and validators run again. Fresh
reconstruction initializes private attributes anew. `mutate()` installs validated
fields and metadata on the existing instance while retaining its private state.

## Resolution, documents, and display

`model_resolve()` returns a shallow copy when discovery finds no factories.
Otherwise it invokes the [resolver](_factory_resolution.md) under CLI suppression
and returns a generated model with resolved annotations. Other sources remain active.

The wrap serializer first honors Pydantic filtering and field serializers. A truthy
`make` serialization context then prefixes `@call`. Factories identify their target
and emit only constructor fields, translating aliases back to canonical keywords.
Existing `@call` keys and ambiguous serialized constructor names raise errors.

Format methods delegate to [\_formats](_formats.md), or `tomllib` for TOML loading.
Display methods import [\_info](_info.md) lazily. `info()` displays stored values;
it does not display provenance or evaluate serializers. All display modes need Rich.
Both `info()` and `model_info()` omit `Field(repr=False)` rows by default;
`respect_field_repr=False` includes them. This affects top-level rows only,
independently of serialization exclusions and nested representations.

## When changing this module

Preserve active per-call validation options, recursive schema references, dynamic
dispatch through subclass hooks, and alias-aware metadata reconciliation. Custom
constructors retain upstream limitations. Nested reconstruction has a separate
option-forwarding limitation recorded in [BUGS.md](../../../BUGS.md). Keep transient
state out of model classes and callbacks so dynamic classes remain serializable.

Evidence: [source](../../../confidantic/_config/base.py),
[copy/serialization tests](../../../tests/_config/test_base.py),
[settings tests](../../../tests/_config/test_settings.py), and
[process tests](../../../tests/integration/test_serialization.py).
See [configuration models](../../concepts/configuration-models.md),
[defining configuration](../../examples/defining-config.md), and [the index](README.md).
