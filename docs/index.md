---
icon: lucide/house
---

# Confidantic

[![PyPI](https://img.shields.io/pypi/v/confidantic)](https://pypi.org/project/confidantic/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/confidantic?logo=python)](https://pypi.org/project/confidantic/)
[![CI](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/ci.yaml?branch=master&logo=github&label=CI)](https://github.com/sztal/confidantic/actions/workflows/ci.yaml)
[![Package build](https://img.shields.io/github/actions/workflow/status/sztal/confidantic/release.yaml?branch=master&logo=github&label=package%20build)](https://github.com/sztal/confidantic/actions/workflows/release.yaml)
[![Coverage](https://sztal.github.io/confidantic/coverage.svg)](coverage/)
[![License](https://img.shields.io/github/license/sztal/confidantic)](https://github.com/sztal/confidantic/blob/master/LICENSE)

Confidantic helps you give a Python application clear, validated settings. Define
fields once, supply values from Python, environment variables, or a command line,
and get useful errors when an input is wrong.

```pycon
>>> from confidantic import BaseConfig
>>> class AppConfig(BaseConfig):
...     name: str = "orders"
...     retries: int = 3
>>> config = AppConfig(retries=5)
>>> print(config.model_dump())
{'name': 'orders', 'retries': 5}

```

It builds on [Pydantic models][pydantic.BaseModel] and
[Pydantic Settings][pydantic_settings.BaseSettings]. Confidantic adds rules for
configuration inheritance, validated updates, and ways to construct application
objects from settings. You can start with a few fields and add those capabilities
when your application needs them.

## Start here

- **New to Confidantic?** [Install it](getting-started/installation.md), then
    [configure your first application](getting-started/first-application.md).
- **Already using Pydantic?** Compare
    [Pydantic, Pydantic Settings, and Confidantic](getting-started/confidantic-vs-pydantic.md).
- **Working on an application?** Learn about [input sources](guide/sources.md),
    [command-line options](guide/cli.md), and [nested settings](guide/nested-settings.md).
- **Building objects from configuration?** Start with [factories](guide/factories.md)
    or [objects that own their configuration](recipes/configurable-objects.md).
- **Want to understand the design?** Read the [concepts](concepts/values-and-inheritance.md)
    and [architecture overview](architecture/overview.md).
- **Looking up a name or option?** Use the [reference](reference/index.md).
- **Contributing?** Follow [setup and checks](contributing.md),
    [agent workflows](agent-skills.md), and [merging and releasing](releasing.md).

## Installation

The core package requires Python 3.13 or later. See
[installation and optional extras](getting-started/installation.md).

## Frozen configuration

Fields are frozen by default. Learn how to [create validated copies and choose an
update operation](guide/settings.md#frozen-configuration).

## Field documentation

Add field descriptions for people reading help or inspecting settings. See
[field documentation](guide/descriptions-and-display.md#field-documentation).

## Configuration display

Use the optional Rich integration to inspect settings. See
[configuration display](guide/descriptions-and-display.md#configuration-display).

## Make directives

For trusted documents that construct Python objects, see
[Make directives](advanced/object-directives-and-portability.md#make-directives).

## YAML and TOML

Learn to [read and write configuration documents](guide/files.md#yaml-and-toml)
and register files as settings sources.
