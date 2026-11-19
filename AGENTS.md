# Confidantic agent guide

## Project overview

- Distribution: `confidantic`
- Import package: `confidantic`
- Source directory: `confidantic/`
- Tests: `tests/`
- Test layout mirrors `confidantic/`: top-level module tests live directly in
  `tests/`, and configuration internals live in `tests/_config/`. Cross-module
  subprocess and example checks live in `tests/integration/`; maintenance-script
  tests live in `tests/scripts/`. See `tests/README.md` for placement conventions.
- Documentation: `docs/`
- Runnable examples: `examples/` (including `factory_dynamic_template.py` and
  `factory_template.py` for recursive `__recursive__` generation)
- Release notes: `changelog.d/` managed by Towncrier
- Agent workflows: `.github/skills/`
- `Factory.model_from(..., __recursive__=...)` can turn matching concrete defaults
  into nested generated `Factory` fields; the generated factory annotation also
  enables nested CLI options such as `--database.host`.
- Repository: https://github.com/sztal/confidantic

Configuration and CLIs for Python projects based on Pydantic and Pydantic Settings.
The package requires Python 3.13 or later; the repository's default interpreter
is read from `.python-version` (currently Python 3.15).

The package root re-exports `BaseConfig`, `ClassDefaultsSource`,
`ConfigModelDict`, `Factory`, and `__version__`. `Factory`
provides `model_from`, `instance_from`, and `instance` for target construction.
Both `Factory` and `BaseConfig` use the inherited `model_resolve` to preserve the
root configuration and resolve nested factory values. Root-only `__include__`
and `__exclude__` selectors support partial factories with runtime inputs. Other
core public APIs live in
`confidantic/annotations.py`, `confidantic/configurable.py`,
`confidantic/context.py`, `confidantic/logging.py`, `confidantic/paths.py`,
`confidantic/types.py`, and `confidantic/utils.py`. Internal configuration
primitives live in `confidantic/_config/`, which contains base and factory
configuration and is re-exported where appropriate by the package root.

## Working conventions

Read and follow [STYLE.md](STYLE.md) before changing Python code or tests.
`pyproject.toml` is the source of truth for dependency groups, Ruff, mypy,
pytest, and coverage configuration.

Set up the development environment with `uv sync --group dev`; add the `docs`
group when building documentation. The repository default interpreter is read
from `.python-version` (currently 3.15). Examples are executable scripts;
`tests/integration/test_examples.py` lists the smoke-tested scripts; check that
file when adding or changing a guide.

Keep changes focused, preserve public behavior unless the task intentionally
changes it, and add or update tests for behavior changes.

Do development work on dedicated branches. Use the `merge-branch` entry point
or `merge-to-master` for the existing isolated, ancestry-preserving merge helper;
do not replace it with a squash merge.

Write release notes only when merging a feature/development branch into `master`.
Ordinary development and bug-fixing tasks do not add Towncrier fragments. Use the
`merge-to-master` skill to summarize the final integrated behavior once per merge;
documentation-only and internal merges record a no-notes reason. The
`release-package` skill assembles these notes when preparing a final release.
Package versions come from annotated Git tags, never a static version field.
See `docs/releasing.md` for commands, setup, and recovery.

## Project records

Use `BUGS.md` as the only repository backlog for confirmed, unresolved source
defects. Record the source file and line, a concise symptom, minimal reproduction
or evidence, affected behavior, and expected behavior. Investigations and test
audits record confirmed source bugs instead of fixing them. Investigations may
update only this ledger; other source, tests, configuration, and documentation
remain read-only. Remove entries proven stale or already fixed, and remove newly
resolved entries only after regression tests and required checks pass. Create the
ledger if missing and never delete it, even when empty.

Use `wiki/` for durable architecture, design decisions, investigations, and
technical reference material. Never use wiki pages for bug tracking or
task-session notes. Preserve the existing `concepts/`, `architecture/`, `api/`,
and `examples/` sections. Wiki guides link to runnable scripts in `examples/`;
the wiki itself is not collected by default pytest or the documentation build.

## Validation

Agents must run the Nox lint session before pytest. Pre-commit may apply
formatting or lockfile updates, so linting after pytest can invalidate the test
result. The standard checks are:

```console
uv run noxfile.py -s lint
uv run pytest
make typecheck
uv run noxfile.py -s docs
```

The `[tool.project-checks]` settings in `pyproject.toml` control type-checking
level (`none`, `basic`, or `strict`), scope, and required/advisory validation.
Defaults are basic, source-only, and required. `make typecheck` propagates errors;
`make check-typecheck` honors `require_typecheck` in shared local and CI checks.
Both skip mypy when the level is `none`. The Nox session uses the same level and
scope, accepts explicit positional overrides, and propagates errors. Source-only
checking includes `confidantic/`; broader checking is opt-in and includes tests,
scripts, and `noxfile.py`. Existing explicit mypy diagnostics remain enabled in
basic mode. Report unavailable or failing checks rather than assuming success.

Use coverage only when statistics are needed. After linting, isolate its data:

```console
coverage_dir=$(mktemp -d)
COVERAGE_FILE="$coverage_dir/.coverage" make coverage
```

Keep the temporary path in the report when its data will be useful. Without an
override, the coverage target uses `.coverage` in the repository. Avoid stale
paths after moved or deleted files by using fresh data; do not erase another
contributor's coverage. The Nox test session also uses temporary coverage data
by default, runs pytest with xdist, combines its data, and reports coverage.

`make test` runs direct `uv run pytest` and is suitable for agents. Do not run
`make nox`, `nox -s tests`, or `uv run noxfile.py -s tests` as an agent: the
supported-Python matrix is reserved for human contributors. Use `uv run pytest`
for the repository suite and focused tests.

Agents may use the non-test Nox sessions directly when a focused check is
needed:

```console
uv run noxfile.py -s lint
uv run noxfile.py -s typecheck
uv run noxfile.py -s docs
```

Pytest is configured to collect tests and doctests from `docs/`,
`confidantic/`, `tests/`, and `README.md`. Documentation builds use
`zensical.toml` and require the `docs` dependency group.

## Documentation

Documentation lives in `docs/`. Build it with the applicable command below
before submitting documentation changes.

```console
uv run noxfile.py -s docs
```
