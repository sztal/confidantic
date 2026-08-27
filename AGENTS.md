# Confidantic agent guide

## Project overview

- Distribution: `confidantic`
- Import package: `confidantic`
- Source directory: `confidantic/`
- Tests: `tests/`
- Repository: https://github.com/sztal/confidantic

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.

## Working conventions

Read and follow [STYLE.md](STYLE.md) before changing Python code or tests.
`pyproject.toml` is the source of truth for dependency groups, Ruff, mypy,
pytest, and coverage configuration.

Keep changes focused, preserve public behavior unless the task intentionally
changes it, and add or update tests for behavior changes.

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

Agents must use standard pytest for test validation and the Nox lint session for
repository checks:

```console
uv run pytest
uv run noxfile.py -s lint
```

Use the coverage target only when coverage statistics are needed:

```console
make coverage
```

Do not run the full Nox test matrix through `make test`, `nox -s tests`, or
`uv run noxfile.py -s tests`. Full multi-version Nox testing is reserved for a
human contributor.

Agents may use the non-test Nox sessions directly when a focused check is
needed:

```console
uv run noxfile.py -s lint
uv run noxfile.py -s typecheck
```

## Documentation

Documentation lives in `docs/`. Build it with the applicable command below
before submitting documentation changes.

```console
uv run noxfile.py -s docs
```
