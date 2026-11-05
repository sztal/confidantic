# confidantic.paths

`ExtensiblePath` is a concrete pathlib path subclass with callable joining.
`BasePaths` is a settings model that canonicalizes path fields and path-valued
extras. `_canonicalize_path` is their private normalization helper.

## Ordered resolution

The ExtensiblePath schema first validates as `Path`, then constructs the platform's
concrete subclass. Calling a path delegates to joining and preserves its concrete
type; it does not separately expand or resolve the result.

BasePaths validates field annotations at subclass creation. All declared fields
must be concrete Path-compatible types; optional or union annotations are rejected.
Pydantic validates field values before the model's after-validator processes root,
declared fields in order, and extras in input order.

Root is expanded and resolved independently. A relative secondary path joins root,
or an earlier anchor when its first segment is `@name`. Absolute paths bypass joining.
Unknown and forward anchors raise a validation error. Existing symlinks are resolved
and `~` is expanded, but directories are not created and paths need not exist.
Existence constraints run earlier, so a relative FilePath is checked against the
working directory before root joining.

## State and updates

The validator replaces fields with canonical ExtensiblePath values using frozen
assignment bypasses, retaining field/source metadata. Relative definitions are
not stored. Changing root alone therefore cannot relocate existing absolute values;
the caller must supply new relative definitions for affected fields.

When editing this module, preserve processing order, typed extras, no filesystem
creation, and validation-before-canonicalization behavior. BasePaths subclasses
extend the path fields; they do not provide a deferred dependency graph.

Evidence: [source](../../confidantic/paths.py) and
[path tests](../../tests/test_paths.py).
See [configuration models](../concepts/configuration-models.md),
[the path guide](../examples/paths.md), and [all modules](README.md).
