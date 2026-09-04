# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=main&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![Package build](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/release.yaml?branch=main&logo=github&label=package%20build)](https://github.com/sztal/confidantic/actions/workflows/release.yaml)
[![Coverage](https://sztal.github.io/confidantic/coverage.svg)](https://sztal.github.io/confidantic/coverage/)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/main/LICENSE)

Configuration and CLIs for Python projects based on Pydantic and Pydantic
Settings. Confidantic requires Python 3.11 or later.

Confidantic extends Pydantic Settings with frozen, validated configuration
models, inheritance-aware source resolution, constructor-derived factories,
context-local state, and portable configuration documents.

## Installation

Install the latest release from [PyPI](https://pypi.org/project/confidantic/)
with [pip](https://pip.pypa.io/) or [uv](https://docs.astral.sh/uv/):

```console
pip install confidantic
uv add confidantic
```

Install optional YAML and TOML serialization support individually with the
`yaml` or `toml` extra, or install both with `all`:

```console
pip install "confidantic[all]"
uv add "confidantic[all]"
```

Install directly from [GitHub](https://github.com/sztal/confidantic) to use an
unreleased change, a branch, or a tag:

```console
pip install "confidantic @ git+https://github.com/sztal/confidantic.git@<tag-or-branch>"
uv add "confidantic @ git+https://github.com/sztal/confidantic.git@<tag-or-branch>"
```

Replace `<tag-or-branch>` with a reference such as `v1.2.3` or `main`. Omit the
`@<tag-or-branch>` suffix to install the repository's default branch.

## Quick start

Define a configuration model with the sources your application needs. When CLI
parsing is enabled, values are resolved in this order: CLI arguments, explicit
initialization arguments, environment variables, dotenv values, secret files,
and class defaults.

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
		model_config = ConfigModelDict(
				env_prefix="APP_",
				env_file=".env",
				cli_parse_args=True,
		)

		name: str = "demo"
		retries: int = 3


config = AppConfig()
updated = config.copy(retries=5)
```

`BaseConfig` keeps Pydantic validation while resolving each configuration
class before its parents in the Python MRO. Nested values can be filled by
lower-priority sources, and `model_field_sources` records field-level source
provenance. Structured JSON, TOML, YAML, and `pyproject.toml` sources are
opt-in through Pydantic Settings source customization.

## Design and functionality

Use the package according to the shape of the configuration problem:

- **Application settings:** `BaseConfig` and `ConfigModelDict` provide frozen
  models, environment and dotenv input, CLI parsing, inherited defaults, and
  source provenance.
- **Configured components:** `Factory` and `FactoryField` generate validated
  configuration from constructor signatures, then materialize the target
  object.
- **Scoped runtime state:** `BaseContext` provides context-local settings with
  persistent and temporary overrides.
- **Flexible inputs:** annotations such as `AbsolutePath`, `CommaDelimited`,
  `Map`, `Import`, `Call`, and `Make` adapt common environment and document
  formats while retaining Pydantic validation.
- **Integrations:** path-aware configuration, configurable classes, and
  logging settings are available through `confidantic.paths`,
  `confidantic.configurable`, and `confidantic.logging`.
- **Portable documents:** trusted `Make` directives can restore concrete
  configuration types; optional YAML and TOML extras provide serialization
  and validation helpers.

## Common use cases

### Constructor-derived components

Generate configuration for a component directly from its constructor:

```python
from confidantic import BaseConfig, Factory, FactoryField


class Service:
		def __init__(self, host: str = "localhost", port: int = 8000) -> None:
				self.host = host
				self.port = port


class Config(BaseConfig):
		service: FactoryField[Service] = Factory.model_from(Service)


config = Config(service=Factory.model_from(Service("api.example.com")))
service = config.service().materialize()
```

See [`examples/factory.py`](examples/factory.py) and
[`examples/factory_gated.py`](examples/factory_gated.py) for nested and
conditional factory patterns.

### Context-local settings

Keep request- or task-specific configuration available without threading it
through every function:

```python
from confidantic.context import BaseContext


class RequestContext(BaseContext):
		request_id: str = "default"


with RequestContext.temporary(RequestContext(request_id="request-42")):
		assert RequestContext.current().request_id == "request-42"
```

See [`examples/context.py`](examples/context.py) for persistent and temporary
overrides.

## Examples and documentation

The [examples/](examples/) directory contains runnable, VS Code cell-delimited
guides with the details:

- [`basic.py`](examples/basic.py), [`cli.py`](examples/cli.py), and [`multilevel_cli.py`](examples/multilevel_cli.py): settings sources, environment variables, and CLI input.
- [`env_files.py`](examples/env_files.py): explicit single- and multi-file dotenv configuration plus automatic discovery.
- [`delimited.py`](examples/delimited.py): comma-delimited lists and flexible `key=value` mappings from environment values or standard Pydantic Settings CLI input.
- [`nested.py`](examples/nested.py), [`factory.py`](examples/factory.py), and [`factory_gated.py`](examples/factory_gated.py): nested, path-aware, and constructor-derived configuration.
- [`configurable.py`](examples/configurable.py): instance configuration for configurable classes.
- [`context.py`](examples/context.py): context-local configuration and scoped overrides.
- [`logging_config.py`](examples/logging_config.py): logging configuration.
- [`directive_annotations.py`](examples/directive_annotations.py) and [`serialization.py`](examples/serialization.py): trusted portable documents and YAML/TOML serialization.

Run a guide as a script or open it in VS Code's Python Interactive Window. The
project smoke-tests every example.

For deeper design and API details, see the [API reference](docs/reference/api.md)
and the focused wiki pages on [configuration resolution](wiki/configuration-resolution.md),
[factories and annotations](wiki/factories-and-annotations.md), and
[contexts and serialization](wiki/contexts-and-serialization.md).

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the
repository, and install the default Python version plus all contributor and
documentation dependencies:

```console
git clone https://github.com/sztal/confidantic.git
cd confidantic
uv python install 3.13
uv sync --group dev --group docs
```

Run the checks used by CI:

```console
uv run noxfile.py -s lint
uv run pytest
uv run noxfile.py -s typecheck
uv run noxfile.py -s docs
```
