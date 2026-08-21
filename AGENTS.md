# Confidantic agent guide

## Project overview

- Distribution: `confidantic`
- Import package: `confidantic`
- Source directory: `src/confidantic/`
- Tests: `tests/`
- Repository: https://github.com/sztal/confidantic

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.

## Working conventions

Read and follow [STYLE.md](STYLE.md) before changing Python code or tests.
`pyproject.toml` is the source of truth for dependency groups, Ruff, mypy,
pytest, and coverage configuration.

Keep changes focused, preserve public behavior unless the task intentionally
changes it, and add or update tests for behavior changes.

## Development notes

Use `wiki/` to record concise, task-specific context during development.
Read [wiki/example.md](wiki/example.md) before starting a note, and
replace it with notes that capture decisions, validation results, and useful
follow-up work.

## Validation

Use the generated Nox script to run automation:

```console
uv run noxfile.py -s lint
uv run noxfile.py -s typecheck
uv run noxfile.py -s tests
```

## Documentation

Documentation lives in `docs/`. Build it with the applicable command below
before submitting documentation changes.

```console
uv run noxfile.py -s docs
```
