# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=master&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![Package build](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/release.yaml?branch=master&logo=github&label=package%20build)](https://github.com/sztal/confidantic/actions/workflows/release.yaml)
[![Coverage](https://sztal.github.io/confidantic/coverage.svg)](https://sztal.github.io/confidantic/coverage/)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/master/LICENSE)

Confidantic lets you define application settings as typed Python classes and
read their values from code, environment variables, or the command line. It
builds on Pydantic and Pydantic Settings to validate those inputs. Factories and
object templates let you use the same approach to construct application components.

```python
import os
from confidantic import BaseConfig
from confidantic.annotations import CommaDelimited

os.environ["APP_TAGS"] = "a,b"

class AppConfig(BaseConfig, env_prefix="APP_"):
    name: str = "orders"
    retries: int = 3
    tags: CommaDelimited[tuple[str, ...]] = ()


config = AppConfig(retries=5)
print(config.model_dump())
```

```text
{'name': 'orders', 'retries': 5, 'tags': ('a', 'b')}
```

**[Follow the first-application tutorial](https://sztal.github.io/confidantic/getting-started/first-application/)**
for a step-by-step introduction.

## Installation

Confidantic requires Python 3.11 or later. Install with pip:

```console
python -m pip install confidantic
```

Or add it to a uv-managed project:

```console
uv add confidantic
```

The core package supports all examples below. Optional extras provide:

| Extra        | Feature                                                    |
| ------------ | ---------------------------------------------------------- |
| `rich`       | Inspect settings with `model_info()` and `info()`          |
| `docstrings` | Generate class `Attributes` sections from `@attrs` markers |
| `yaml`       | YAML loading and dumping                                   |
| `toml`       | TOML dumping; loading is included in the core package      |
| `all`        | All optional features                                      |

For example, install every extra with:

```console
python -m pip install "confidantic[all]"
```

To try unreleased code from GitHub:

```console
python -m pip install "confidantic @ git+https://github.com/sztal/confidantic.git@master"
```

Replace `master` with another branch or a tag to select that revision. See the
[installation guide](https://sztal.github.io/confidantic/getting-started/installation/)
for environment setup and optional features.

## How it works

Pydantic validates fields; Pydantic Settings supplies input sources and CLI
parsing. Confidantic adds configuration inheritance rules, validated updates,
and ways to construct application objects from those settings.

Fields are frozen by default. Use `config.copy(retries=6)` to create a validated
updated copy. Nested mutable values are not recursively frozen, and updated
copies can consult settings sources again. See [settings and updates](https://sztal.github.io/confidantic/guide/settings/).

Enable environment and CLI input explicitly through `ConfigModelDict`. Within
one class, enabled sources normally take priority in this order: CLI, Python
initializer arguments, environment, dotenv, secret files, then declared defaults.
A child's sources and defaults precede its parents', so a child default can beat
a parent environment value. The [sources guide](https://sztal.github.io/confidantic/guide/sources/)
and [inheritance explanation](https://sztal.github.io/confidantic/concepts/values-and-inheritance/)
cover the details.

## Examples

### CLI and environment

Use the same fields for Python inputs, environment variables, and command-line
options. Save this complete program as `app.py`:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
    model_config = ConfigModelDict(env_prefix="APP_", cli_parse_args=True)

    name: str = "orders"
    retries: int = 3


print(AppConfig().model_dump())
```

```console
python app.py --name shipping --retries 5
```

```text
{'name': 'shipping', 'retries': 5}
```

The same fields accept `APP_NAME` and `APP_RETRIES` environment variables; CLI
values take priority. Read the [CLI guide](https://sztal.github.io/confidantic/guide/cli/)
for help, nested options, and subcommands.

### Factories

Derive configuration from an annotated constructor instead of declaring its
parameters twice. A dataclass provides a small example:

```python
from dataclasses import dataclass

from confidantic import Factory


@dataclass
class Service:
    host: str
    port: int = 8000


ServiceConfig = Factory.model_from(Service)
config = ServiceConfig(host="api.example.com", port=8080)
service = config.model_resolve()
print(service)
```

```text
Service(host='api.example.com', port=8080)
```

`model_from()` generates a configuration class, instantiating it validates the
inputs, and `model_resolve()` constructs the service. See the
[factory guide](https://sztal.github.io/confidantic/guide/factories/).

### Templates

An existing object can supply configuration defaults. Continuing with `Service`
and `Factory` from the preceding example:

```python
template = Service("api.example.com", 8000)
TemplateConfig = Factory.model_from(template)
config = TemplateConfig(port=9000)
service = config.model_resolve()
print(service)
print(template)
```

```text
Service(host='api.example.com', port=9000)
Service(host='api.example.com', port=8000)
```

The new service uses the overridden port; the original template is unchanged.
Read about [object templates](https://sztal.github.io/confidantic/guide/factories/#use-an-object-as-a-template)
or [recursive templates and runtime type selection](https://sztal.github.io/confidantic/advanced/dynamic-template-clis/).

### Smart annotations

Accept convenient text inputs while validating the types of individual values:

```python
from confidantic import BaseConfig
from confidantic.annotations import CommaDelimited, Map


class WorkerConfig(BaseConfig):
    ports: CommaDelimited[list[int]]
    limits: Map[dict[str, int]]


config = WorkerConfig(ports="8000,9000", limits="workers=4,retries=3")
print(config.model_dump())
```

```text
{'ports': [8000, 9000], 'limits': {'workers': 4, 'retries': 3}}
```

See [input parsing](https://sztal.github.io/confidantic/guide/input-parsing/)
for other separators, mappings, and paths.

For other application needs, explore [contexts](https://sztal.github.io/confidantic/recipes/contexts/),
[configured objects](https://sztal.github.io/confidantic/recipes/configurable-objects/),
[paths](https://sztal.github.io/confidantic/recipes/paths/),
[logging](https://sztal.github.io/confidantic/recipes/logging/), and
[file formats](https://sztal.github.io/confidantic/guide/files/).
The [examples directory](https://github.com/sztal/confidantic/tree/master/examples)
contains complete runnable scripts.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone
the repository and set up the development environment:

```console
git clone https://github.com/sztal/confidantic.git
cd confidantic
uv python install
uv sync --group dev --group docs --extra all
```

`uv python install` reads the repository's `.python-version`. Run the checks in
this order so formatting happens before tests:

```console
uv run noxfile.py -s lint
uv run pytest
uv run noxfile.py -s typecheck
make docs
```

`make docs` builds the documentation into `site/`. Use `make docs-serve` for a
local preview that reloads when you edit the Markdown sources.

Start with the [architecture overview](https://sztal.github.io/confidantic/architecture/overview/)
and [wiki handbook](https://github.com/sztal/confidantic/blob/master/wiki/README.md)
for the design, then the [implementation reference](https://github.com/sztal/confidantic/blob/master/wiki/api/README.md)
for internals. Follow the [style guide](https://github.com/sztal/confidantic/blob/master/STYLE.md)
and [test-placement guide](https://github.com/sztal/confidantic/blob/master/tests/README.md)
when contributing. See [merging and releasing](https://sztal.github.io/confidantic/releasing/)
for distribution checks (including optional dependencies), release notes, and publication.
