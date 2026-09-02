# Confidantic agent guide

## Project overview

- Distribution: `confidantic`
- Import package: `confidantic`
- Source directory: `confidantic/`
- Tests: `tests/`
- Documentation: `docs/`
- Runnable examples: `examples/`
- Release notes: `changelog.d/` managed by Towncrier
- Repository: https://github.com/sztal/confidantic

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.
The package requires Python 3.11 or later; the repository's default interpreter
is Python 3.13.

The core public APIs live in the package root and in
`confidantic/annotations.py`, `confidantic/configurable.py`,
`confidantic/context.py`, `confidantic/logging.py`, `confidantic/paths.py`,
`confidantic/types.py`, and `confidantic/utils.py`. Internal configuration
primitives live in `confidantic/_config/`, which contains base and factory
configuration and is re-exported where appropriate by the package root.

## Working conventions

Read and follow [STYLE.md](STYLE.md) before changing Python code or tests.
`pyproject.toml` is the source of truth for dependency groups, Ruff, mypy,
pytest, and coverage configuration.

Set up the development environment with `uv sync --group dev`. Examples are
executable scripts and are smoke-tested by `tests/test_examples.py`.

Keep changes focused, preserve public behavior unless the task intentionally
changes it, and add or update tests for behavior changes.

Add a Towncrier fragment under `changelog.d/` for every user-visible behavior
change, bug fix, or public API change. Do this as part of the same change, not
as a later release step. Documentation-only and strictly internal changes do
not need a fragment.

## Project records

Use `BUGS.md` as the only repository backlog for confirmed, unresolved source
defects. Record a concise symptom, reproduction or evidence, affected behavior,
and expected behavior. Test audits add confirmed source bugs there instead of
fixing them. Bug-fixing tasks remove resolved entries after their regression
tests and required checks pass.

Use `wiki/` for durable architecture, design decisions, investigations, and
technical reference material. Never use wiki pages for bug tracking or
task-session notes.

## Validation

Agents must run the Nox lint session before pytest. Pre-commit may apply
formatting or lockfile updates, so linting after pytest can invalidate the test
result:

```console
uv run noxfile.py -s lint
uv run pytest
```

Use the coverage target only when coverage statistics are needed:

```console
uv run coverage erase
make coverage
```

The coverage target uses the repository's `.coverage` file. Erase it first
when files have been moved or deleted; otherwise `coverage report` can retain
stale paths and fail with `No source for code`. The Nox test session uses a
temporary coverage file by default, runs pytest with xdist, combines its data,
and reports coverage.

Do not run the full Nox test matrix through `make test`, `nox -s tests`, or
`uv run noxfile.py -s tests`. Full multi-version Nox testing is reserved for a
human contributor.

Agents may use the non-test Nox sessions directly when a focused check is
needed:

```console
uv run noxfile.py -s lint
uv run noxfile.py -s typecheck
uv run noxfile.py -s docs
```

## Documentation

Documentation lives in `docs/`. Build it with the applicable command below
before submitting documentation changes.

```console
uv run noxfile.py -s docs
```
