# Install Confidantic

Use Python 3.11 or later. A virtual environment keeps your application's
packages separate from other projects.

=== "pip"

    ```console
    python -m venv .venv
    ```

    Activate it with `source .venv/bin/activate` on macOS/Linux, or
    `.venv\Scripts\Activate.ps1` in Windows PowerShell, then install:

    ```console
    python -m pip install confidantic
    ```

=== "uv"

    In a project managed by uv:

    ```console
    uv add confidantic
    ```

    Use `uv run python app.py` wherever the guides show `python app.py`.

The core package includes settings, CLI parsing, factories, contexts, path and
logging helpers, and attribute-docstring extraction. The first tutorial needs
only this installation. You do not need to clone the Confidantic repository.

## Optional extras

| Extra        | Adds                                                 |
| ------------ | ---------------------------------------------------- |
| `rich`       | `model_info()` and `info()` display methods          |
| `docstrings` | Class-docstring generation from an `@attrs` marker   |
| `yaml`       | YAML loading and dumping                             |
| `toml`       | TOML dumping; reading TOML uses the standard library |
| `all`        | All optional features                                |

For example, install YAML support with either command:

=== "pip"

    ```console
    python -m pip install "confidantic[yaml]"
    ```

=== "uv"

    ```console
    uv add "confidantic[yaml]"
    ```

Extras can be combined, as in `confidantic[rich,yaml]`. Each optional package is
imported when its feature is used. A missing dependency raises `ImportError`
with the extra to install; unrelated core features remain available.

Continue with [your first application](first-application.md).
