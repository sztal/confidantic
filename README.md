# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=main&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/main/LICENSE)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.

## Installation

Install `confidantic` using [pip](https://pip.pypa.io/) or [uv](https://docs.astral.sh/uv/):

```
pip install confidantic
```

## Examples

The [examples/](examples/) directory contains runnable, VS Code cell-delimited
guides. Run a file as a script or open it in VS Code's Python Interactive Window.

- `basic.py` and `cli.py`: settings sources, environment variables, and CLI input.
- `directive_annotations.py` and `serialization.py`: trusted portable documents.
- `factory.py` and `factory_gated.py`: constructor-derived configuration.
- `logging_config.py` and `nested.py`: logging settings and nested Pydantic models.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
create a virtual environment:

```bash
uv venv
source .venv/bin/activate
```

Install the package and its development dependencies:

```bash
uv sync --group dev
```

Run the test suite and checks with:

```bash
uv run pytest
uv run pre-commit run --all-files
```
