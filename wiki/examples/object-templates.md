# Configure nested object templates

[factory_template.py](../../examples/factory_template.py) starts with an Application
containing a Database. Install `confidantic[rich]` for its final display call.

```console
uv run python examples/factory_template.py --application.database.host cli.example.com --application.database.port 6543
```

## Generate nested configuration

Excerpt after the Application and Database definitions:

```python
template = Application("orders", Database("db.example.com", 6432))
ApplicationConfig = Factory.model_from(template, __recursive__=Database)
```

The selector matches the concrete database default. That default becomes a nested
factory field with generated constructor annotations, making host and port visible
to validation and CLI parsing. The application name remains `"orders"`.

The root model from the same script is:

```python
class Config(BaseConfig, cli_parse_args=True):
    """Application inputs with nested factory options exposed on the CLI."""

    application: ApplicationConfig = ApplicationConfig()
    """A configuration model for an application with a nested database."""
    log_level: str = "INFO"
    """The log level for the application."""
```

It ends with `Config().model_resolve()`. The resulting application contains a real
Database at `cli.example.com:6543`. The display shows that object, and the
[integration test](../../tests/integration/test_examples.py) asserts its concrete
type, host, port, and unchanged application name.

## Keep the stages separate

`__recursive__` selects defaults during generation. Resolution is always recursive
over supported nested factories. It does not accept field updates; use source input,
validation, or a validated copy before resolving. Required fields with no concrete
default cannot be turned into nested templates by selection alone.

Continue to [dynamic template CLIs](advanced/dynamic-template-clis.md) when the
dependency type itself must be selected at runtime. Read
[factory concepts](../concepts/factories-and-templates.md),
[the builder](../api/_config/_factory_build.md), or [all guides](README.md).
