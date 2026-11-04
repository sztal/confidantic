# Read settings from different sources

A *source* is a place from which configuration values are read. Defaults make an
application runnable; environment variables let you change it between deployments;
Python arguments let a caller provide explicit values.

## Environment and dotenv

Save this as `app.py`:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="APP_", env_file=".env")

    name: str = "orders"
    retries: int = 3


print(AppConfig().model_dump())
```

Create `.env` in the directory from which you run the program:

```dotenv
APP_NAME=warehouse
APP_RETRIES=4
```

`python app.py` prints `{'name': 'warehouse', 'retries': 4}` when no matching
process environment variables are set. Setting `APP_RETRIES=6` in the environment
changes the retry count to `6`; using `AppConfig(retries=7)` changes it to `7`.
See [the tutorial](../getting-started/first-application.md#read-environment-variables)
for shell-specific commands.

`env_prefix=None`, the default, disables process environment reading. A string
prefix enables it; an empty string reads unprefixed names. Dotenv and secret-file
loading are separate and are not disabled by `env_prefix=None`.

Empty environment and dotenv values are ignored by default. The text `null` is
parsed as `None`, which is useful for fields annotated with `str | None` or another
nullable type. Aliases can affect external names; see
[env_prefix_target][confidantic.ConfigModelDict] before combining aliases and prefixes.

## Understand which value wins

For a single class with the usual sources enabled:

| Priority | Source                          |
| -------- | ------------------------------- |
| 1        | CLI arguments, when enabled     |
| 2        | Python initializer arguments    |
| 3        | Process environment             |
| 4        | Dotenv files                    |
| 5        | Secret files                    |
| 6        | Defaults declared on that class |

!!! note "Inheritance has its own priority"

    A child's sources and directly declared defaults come before its parents'
    sources and defaults. A child default can therefore beat a parent environment
    value. Read [values and inheritance](../concepts/values-and-inheritance.md)
    before treating this table as the order across several classes.

All configured sources still run. A malformed lower-priority value can raise an
error even when a higher-priority source provides the same field.

## Use several dotenv files

Set `env_file=(".env", ".env.local")` in `ConfigModelDict`. Later files override
earlier files. The default dotenv filtering keeps variables matching declared
fields, allowing a shared dotenv file to contain settings for other components.

Prefer explicit paths initially. Automatic discovery is opt-in through
`env_file_discovery=True`. Override `find_dotenv()` if your application needs a
specific search location: the default script search begins at the helper's source
directory, which need not be your application's directory.

When discovery is enabled, even `_env_file=None` requests discovery; disable
`env_file_discovery` as well when you want to suppress it. See the
[options reference](../reference/options.md) for filtering and discovery controls.

## Read a secret file

For a local demonstration, create `secrets/APP_TOKEN` containing `example-token`.
Use this complete program from the directory containing `secrets/`:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="APP_", secrets_dir="secrets")

    token: str


config = AppConfig()
print(bool(config.token))
```

It prints `True` without displaying the token. Environment and initializer values
can still override the file. In a deployed application, point `secrets_dir` at
the directory supplied by your deployment system.

## Explain a value's origin

The `model_field_sources` mapping records each field's source class and the
configuration class that supplied it:

```pycon
>>> from confidantic import BaseConfig
>>> class AppConfig(BaseConfig):
...     retries: int = 3
>>> source, owner = AppConfig().model_field_sources["retries"]
>>> source.__name__, owner.__name__
('ClassDefaultsSource', 'AppConfig')

```

This is provenance: where a value came from. It reports the first source that
established a top-level field, not the origin of every nested key. Extras and
computed fields are omitted. Bare callable sources disable automatic provenance.

For structured documents, continue with [files](files.md). For replacing or
reordering sources, see [custom sources](../advanced/custom-sources.md).
