# Select dependency types before generating CLI options

[factory_dynamic_template.py](../../../examples/factory_dynamic_template.py) needs
`confidantic[rich]` for display. It extends the [object template guide](../object-templates.md)
by selecting the database class before generating the final application model.

```console
uv run python examples/factory_dynamic_template.py --types.database __main__:ExtendedDatabase --application.database.host cli.example.com --application.database.port 6543
uv run python examples/factory_dynamic_template.py --help.types true --help
uv run python examples/factory_dynamic_template.py --help
```

## Three parser stages

HelpRouter first reads the help destination without installing standard help. Types
then accepts `Import[type[Database]]` under the `types` prefix, enabling its help
only when requested. Both stages ignore options intended for later stages.

This excerpt follows `types = Types()`:

```python
template = Application("orders", types.database())
ApplicationConfig = Factory.model_from(template, __recursive__=Database)
```

The selected class is instantiated to create the concrete template, so it must be
constructible at this stage. Generation then exposes its constructor fields to the
final Config parser. That parser accepts dotted application/database options and
model_resolve constructs the selected runtime objects.

## Expected behavior

The first command produces an Application named orders with an ExtendedDatabase
at `cli.example.com:6543`. The existing integration test asserts the selected type
and overridden fields. ExtendedDatabase inherits the constructor and has a separate
class-level switch; that switch does not become a generated constructor field.

The help-router command shows type-selection help, while plain help shows final
application options. `__main__` works because the class is defined in the running
script; reusable documents should name a stable importable module instead.

Read [CLI concepts](../../concepts/clis.md),
[factory generation](../../api/_config/_factory_build.md),
[CLI adaptation](../../api/_config/_cli.md), and [advanced guides](README.md).
