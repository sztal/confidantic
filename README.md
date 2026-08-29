# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=main&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![Package build](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/release.yaml?branch=main&logo=github&label=package%20build)](https://github.com/sztal/confidantic/actions/workflows/release.yaml)
[![Coverage](https://sztal.github.io/confidantic/coverage.svg)](https://sztal.github.io/confidantic/coverage/)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/main/LICENSE)

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.

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

## Features

`confidantic` provides frozen, validated Pydantic Settings models, configurable
settings sources, and CLI support. It also includes context-local, factory, and
path-aware configuration; logging settings; and trusted portable configuration
documents with Make directives and optional YAML/TOML serialization.

The [examples/](examples/) directory contains runnable, VS Code cell-delimited
guides with the details:

- [`basic.py`](examples/basic.py), [`cli.py`](examples/cli.py), and [`multilevel_cli.py`](examples/multilevel_cli.py): settings sources, environment variables, and CLI input.
- [`nested.py`](examples/nested.py), [`factory.py`](examples/factory.py), and [`factory_gated.py`](examples/factory_gated.py): nested, path-aware, and constructor-derived configuration.
- [`configurable.py`](examples/configurable.py): instance configuration for configurable classes.
- [`logging_config.py`](examples/logging_config.py): logging configuration.
- [`directive_annotations.py`](examples/directive_annotations.py) and [`serialization.py`](examples/serialization.py): trusted portable documents and YAML/TOML serialization.

Run a guide as a script or open it in VS Code's Python Interactive Window. The
project smoke-tests every example.

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
