# confidantic.\_config.\_info

`_InfoRenderer` owns Rich presentation for BaseConfig's `model_info` and `info`
methods. This private module imports Rich normally; the public methods import
the module lazily and translate a missing Rich dependency into an installation hint.

## Build, then render

One renderer retains a model class and presentation options for one display call.
`build_table()` iterates canonical declared fields in model order. It can include
types, supplied current values, defaults, and descriptions. It omits extras and
computed fields. Values use Python representations, not serialization dumps.

Required fields have a marker; default factories display a name and are never
called. Descriptions and names use Rich Text so markup-like field content is
literal. Generic annotations are rendered from their type representation.

`render()` returns the table directly, captures a string in a local StringIO, or
prints through a Console. Unknown output modes raise ValueError. Color requests
affect styling and terminal rendering, but Rich's own environment controls still
apply. Returning a table leaves eventual rendering to the caller.

## When changing this module

Preserve side-effect-free inspection of defaults and stored values. Adding provenance
or extra fields would change the current display contract and needs deliberate
public API work. Keep optional dependency handling at the public operation boundary;
do not import this module during ordinary model creation.

Evidence: [source](../../../confidantic/_config/_info.py) and
[display tests](../../../tests/_config/test_info.py).
See [configuration models](../../concepts/configuration-models.md),
[the CLI display example](../../examples/clis.md), and [the index](README.md).
