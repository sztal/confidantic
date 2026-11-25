# confidantic.utils

Public helpers detect notebook-like runtimes, create/import object identifiers,
and evaluate Make directives. `_call_mapping` implements a single directive and
is shared with the annotation layer.

## Import and runtime helpers

`is_runtime_jupyterlike()` checks for a loaded ipykernel or a ZMQInteractiveShell.
This is a heuristic; an ordinary IPython terminal does not qualify by itself.
`get_import_string` uses singledispatch for modules and otherwise returns
`module:qualname`, falling back to the object's type. It does not test importability.
`import_from_string` delegates import and requested-type validation to a Pydantic
TypeAdapter of ImportString, preserving validation errors.

## Directive evaluation

`_call_mapping` reads `@call`, optional iterable `@args`, and keyword entries.
It neither changes the mapping nor recursively evaluates arguments. A missing
target or non-iterable positional input raises `ValueError`; import and call
errors propagate.

`make` recursively rebuilds mapping values, lists, and tuples before invoking
call mappings. Mapping keys are left alone. Nested ordinary strings and callables
remain data; only top-level strings/callables are called without arguments.
Returned values are not visited again. An optional final handler validates the
completed result once, providing the integration point for `Make[T]`.

The traversal holds no cache, evaluates repeated directives separately, and has
no cycle detector. Recursive inputs can raise `RecursionError`. This differs from
the factory resolver's supported containers and explicit cycle checks.

## When changing this module

Preserve execution order and the boundary between literal data and executable
directives. Do not recursively consume call results or mapping keys. Avoid adding
importability checks to identifier formatting without accounting for local classes
and serialization consumers. Calls can execute arbitrary application code and are
intended for trusted inputs.

Evidence: [source](../../src/confidantic/utils.py) and
[utility tests](../../tests/test_utils.py).
See [input annotations](../concepts/input-annotations.md),
[portable object graphs](../examples/advanced/portable-object-graphs.md),
and [all modules](README.md).
