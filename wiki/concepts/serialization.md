# Serialization and reconstruction

Ordinary model dumps describe values. They do not universally encode concrete
runtime types, constructor identity, or process state. Choose a representation
according to what must be reconstructed.

## Data documents

Use `model_dump` or `model_dump_json` for mappings and JSON, and validate with the
known model class on loading. Broad base-class annotations can omit subclass-only
data unless `serialize_as_any=True` is requested. Ordinary BaseModel values do not
gain a type discriminator merely because they are nested in BaseConfig.

YAML loading/dumping requires the `yaml` extra. TOML dumping requires `toml`; loading
uses Python's standard library. Both public loaders parse values and call model
validation. That validation can consult configured settings sources, so a document
is not necessarily the only input used to construct settings.

TOML cannot represent None. `exclude_none=True` removes nullable model fields but
does not remove None entries inside lists or mappings. YAML can represent null.
Per-call validation options follow BaseConfig's normal validation boundaries.
When comparing a restored model with its original, compare the dumped values if
source provenance is not part of the comparison: equality can include private
state that differs between defaults and explicitly loaded values.

## Trusted construction directives

`context={"make": True}` adds `@call` identifiers to serialized BaseConfig values.
Factories identify their target class and only emit constructor fields, using
canonical keyword names despite serialization aliases. Field serializers and
filtering still apply, so excluding a required argument can make reconstruction fail.

Validate parsed data through `Make[T]` to evaluate directives. YAML/TOML model loaders
do not themselves interpret a root `@call`. Identifiers must resolve to importable
targets in the receiving process; local classes and unregistered generated classes
are not portable identifiers. These documents execute imports and constructors and
are intended for trusted data.

`Make[FromJson[T]]`, `Make[FromYaml[T]]`, and `Make[FromToml[T]]` combine file
reading with directive evaluation and validation as `T`. These annotations work
on fields in nested settings as well as at the root. A bare file annotation reads a
mapping without executing directives. It does not preserve the path for write-back.
See the [file-backed round-trip example](../examples/serialization.md#load-files-inside-nested-configuration).

## Python serialization

Pickle/cloudpickle transfer Python objects and supported dynamic classes under
different assumptions from portable documents. Current process tests exercise dynamic
models, but private layouts and old Python payloads are not a stable interchange
contract. Context activation and temporary validation state stay process-local.

See [serialization examples](../examples/serialization.md),
[portable object graphs](../examples/advanced/portable-object-graphs.md),
[BaseConfig serialization](../api/_config/base.md), and [format helpers](../api/_config/_formats.md).
Return to [all concepts](README.md).
