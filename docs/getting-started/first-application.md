# Configure your first application

We will give a small order-processing application a name and a retry count.
You need only [the core package](installation.md) and an empty working directory.
Run commands from that directory; the tutorial's files live there.

## Define settings

Create `app.py` with this complete program:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
    name: str = "orders"
    retries: int = 3


config = AppConfig()
print(config.model_dump())
```

Run it:

```console
python app.py
```

```text
{'name': 'orders', 'retries': 3}
```

`AppConfig` describes the fields. `config` holds one set of validated values.
The annotation `int` says that `retries` must be an integer; `3` is its default.
`model_dump()` returns a dictionary that is easy to inspect or pass to other code.

## Supply a value from Python

Change `config = AppConfig()` to:

```python
config = AppConfig(retries=5)
```

Running the program now prints `{'name': 'orders', 'retries': 5}`. Restore
`config = AppConfig()` before continuing so the following steps demonstrate
external inputs without a Python override.

## Read environment variables

Change the import to include `ConfigModelDict`:

```python
from confidantic import BaseConfig, ConfigModelDict
```

Add this line inside `AppConfig`, above its fields:

```python
model_config = ConfigModelDict(env_prefix="APP_")
```

Environment loading is now enabled. The prefix maps `APP_NAME` to `name` and
`APP_RETRIES` to `retries`.

=== "macOS / Linux"

    ```console
    APP_NAME=shipping python app.py
    ```

=== "PowerShell"

    ```powershell
    $env:APP_NAME = "shipping"
    python app.py
    Remove-Item Env:APP_NAME
    ```

Both print `{'name': 'shipping', 'retries': 3}`. Without a string `env_prefix`,
process environment variables are not read. Use `""` for names without a prefix.

## Read a dotenv file

Create `.env` next to `app.py`:

```dotenv
APP_NAME=warehouse
APP_RETRIES=4
```

Replace the `model_config` line with:

```python
model_config = ConfigModelDict(env_prefix="APP_", env_file=".env")
```

Run `python app.py` with no `APP_NAME` or `APP_RETRIES` in your shell environment.
It prints `{'name': 'warehouse', 'retries': 4}`. Process environment values take
priority over this file. The relative filename is interpreted from the working
directory, so continue running the program from the directory containing `.env`.

## Add command-line options

Replace `app.py` with this final version. The `main()` function and its guard make
it possible to import `AppConfig` later without running the application.

```python
--8<-- "examples/quickstart.py"
```

`cli_parse_args=True` enables parsing of the process command line. Try:

```console
python app.py --name shipping --retries 6
```

```text
{'name': 'shipping', 'retries': 6}
```

For this single configuration class, enabled inputs normally win in this order:
CLI, Python arguments, environment, dotenv, secret files, then declared defaults.
[Inheritance adds another rule](../concepts/values-and-inheritance.md): a child's
sources and defaults come before its parents' sources and defaults.

## Understand a validation error

Run:

```console
python app.py --retries many
```

The program exits with a validation error for `retries`: `many` cannot be parsed
as an integer. No settings instance is returned. Use `--retries 6` to correct it.
Text such as `"6"` is accepted because it can be converted to the declared type.
The exact traceback formatting depends on the installed Pydantic version.

## Create a validated copy

Keep the final `app.py` and create `update.py`:

```python
from app import AppConfig

config = AppConfig()
updated = config.copy(retries=5)
print(config.retries, updated.retries)
```

With the tutorial's `.env`, no shell overrides, and no CLI arguments,
`python update.py` prints `4 5`. The original is unchanged. Fields are frozen
by default, so copying is the usual way to derive new settings.

!!! note "Updates still use configuration rules"

    An updated copy validates its inputs and can consult settings sources again.
    CLI input can override a copy's update. The example deliberately runs without
    CLI arguments; see [choosing an update operation](../guide/settings.md#frozen-configuration).

You now have one definition for defaults, environment inputs, and command-line
options. Continue with [settings and validation](../guide/settings.md), or add
[nested settings](../guide/nested-settings.md) as the application grows.
