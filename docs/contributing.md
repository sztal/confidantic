# Contribute to Confidantic

Work on a dedicated development branch and preserve unrelated changes in the
checkout. Keep changes focused, update tests for behavior changes, and follow
[AGENTS.md](https://github.com/sztal/confidantic/blob/master/AGENTS.md) and
[STYLE.md](https://github.com/sztal/confidantic/blob/master/STYLE.md).
Ordinary development does not add changelog fragments; notes are consolidated
when a branch is [integrated into master](releasing.md#development-and-merge-notes).

## Set up the checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the
repository, and run:

```console
git clone https://github.com/sztal/confidantic.git
cd confidantic
uv python install
uv sync --group dev --group docs --extra all
```

`uv python install` reads `.python-version`, currently 3.15. The package supports
Python 3.13 and later; Ruff and mypy target 3.13 to preserve that compatibility.
Dependency groups and tool settings live in
[pyproject.toml](https://github.com/sztal/confidantic/blob/master/pyproject.toml).

The Copier template ties the tool targets to its default interpreter. This
project saves the 3.13 target for Ruff and mypy but overrides `.python-version`
to 3.15. Preserve that override, the project's dependencies, and its merge and
release safeguards when updating the template. Review update conflicts before
accepting changes to project-specific settings.

## Place code and tests

The package lives in `src/confidantic/`, with configuration internals under `_config/`.
Follow the [architecture overview](architecture/overview.md) to find the owning
component. Use type hints, double-quoted strings, and NumPy-style docstrings.

Tests mirror the package: configuration internals belong under `tests/_config/`,
subprocess and example checks under `tests/integration/`, and maintenance-script
tests under `tests/scripts/`. Follow the
[test placement guide](https://github.com/sztal/confidantic/blob/master/tests/README.md)
and test observable behavior using existing fixtures where practical.
Confirmed unresolved source defects belong in
[BUGS.md](https://github.com/sztal/confidantic/blob/master/BUGS.md).

## Validate in order

Run from the repository root:

```console
uv run noxfile.py -s lint
uv run pytest
make typecheck
uv run noxfile.py -s docs
```

Lint can rewrite formatting or the lockfile. Review its changes and rerun it
until clean before testing. Pass a test path to pytest for focused checks.
Agents use direct pytest or `make test`; the supported-Python Nox test matrix,
including `make nox`, is reserved for human contributors.

`[tool.project-checks]` controls type-checking level, scope, and required/advisory
policy. Defaults are basic, source-only, and required. `make typecheck` propagates
errors; `make check-typecheck` honors the policy used by shared checks. Both skip
mypy when the level is `none`. See the
[type-checking policy](releasing.md#type-checking-policy) for all settings.

`make check` also builds and checks distributions. Report unavailable or failing
checks instead of assuming success. Use isolated coverage data only when needed,
following the recipe in AGENTS.md.

## Edit documentation

Published pages live in `docs/`, with navigation in `zensical.toml`. `make docs`
builds strictly into `site/`; `make docs-serve` previews locally. Neither command
publishes. Link relatively between published pages and use repository URLs for
files outside `docs/`.

Pytest collects Markdown doctests in `docs/`: use `pycon` blocks with prompts and
stable expected results for executable examples. Ordinary fenced `python` blocks
are not automatically executed. The repository wiki is excluded from the normal
doctest and documentation-build paths, so its snippets and links need separate
verification.

Continue with [agent workflows](agent-skills.md) or [merging and releasing](releasing.md).
The [wiki developer guide](https://github.com/sztal/confidantic/blob/master/wiki/dev/README.md)
contains additional repository-oriented guidance.
