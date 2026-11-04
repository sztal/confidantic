Partial settings updates retain concrete nested model types and existing values
from defaults and default factories. Per-call strictness, extra policy, and
validation context reach settings assembly before user validators; custom
constructors, strict JSON representations, and nested partial reconstruction
retain their documented limitations. Newly added Pydantic Settings source options
are forwarded without requiring matching Confidantic signature changes.

Copy, deepcopy, and mutate honor validation aliases and preserve settings-source
provenance and explicit-field metadata for extras. Configurable equality compares
stored fields and extras consistently with hashing. Empty and current-directory
secondary paths resolve against the configured root. Direct CLI-source
construction works with the default unset environment prefix.

Generated factories isolate mutable defaults, preserve settings merging and union
alternatives, resolve inherited constructor annotations, and retain the target's
module metadata. Validate target compatibility, including compatible subclasses,
and recognize callable typing objects as type selectors without invoking them.
Finite recursive model values resolve while actual value cycles are rejected.
Nested factories in sets initialize correctly on Python 3.14.

Factory Make serialization uses the target import string, constructor fields, and
canonical keyword names; ambiguous aliases and serializer failures propagate.
Cloudpickle restores dynamic configuration/context classes and generated factory
schemas while keeping ambient context local to each interpreter. Static typing
supports specialized factory resolution and `Call`/`Make` annotations.
