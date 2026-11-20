# Contribute a change

After [environment setup](README.md#set-up-the-checkout), inspect the working tree
and create a dedicated development branch from the intended base. Preserve
unrelated work. Keep changes focused and update behavioral tests when public
behavior changes. Ordinary development does not create changelog fragments.

## Code and tests

Follow [STYLE.md](../../STYLE.md): type hints, double-quoted strings, NumPy-style
docstrings, and concise public API documentation. Ruff and mypy configuration
lives in [pyproject.toml](../../pyproject.toml).

Follow the [test placement guide](../../tests/README.md). Module tests mirror the
package, configuration internals belong under `tests/_config/`, subprocess and
example checks under `tests/integration/`, and maintenance-script tests under
`tests/scripts/`. Reuse existing fixtures and test observable behavior.

## Validate in order

Run from the repository root:

```console
uv run noxfile.py -s lint
uv run pytest
make typecheck
uv run noxfile.py -s docs
```

Lint must precede pytest because pre-commit can rewrite formatting or the lockfile.
Review any changes, rerun lint until clean, and then test the resulting files.
For focused reproduction, pass a test path to `uv run pytest` after linting.
Report failing or unavailable checks rather than treating them as passing.

Agents use direct pytest or `make test`. The multi-Python Nox test session,
including `make nox`, is reserved for human contributors. Coverage is optional;
when needed, isolate its data using the temporary `COVERAGE_FILE` recipe in
[AGENTS.md](../../AGENTS.md). Do not erase someone else's coverage data.

`[tool.project-checks]` controls type-checking level (`none`, `basic`, `strict`),
scope, and whether failures block shared checks. Defaults are basic, source-only,
and required. `make typecheck` propagates errors; `make check-typecheck` honors
the required/advisory policy. Both skip mypy when the level is `none`.

`make check` additionally builds and checks distributions after lint, tests,
type checking, and documentation. Merge and release helpers use shared
validation; do not bypass failed checks to integrate a change.

## Documentation boundaries

Published pages live in `docs/`, with navigation in
[zensical.toml](../../zensical.toml). `make docs` builds strictly into `site/`;
`make docs-serve` previews locally. Neither command publishes a site.

The wiki preserves concepts, architecture, API references, runnable-guide links,
and contributor instructions. It is not included in the documentation build or
default pytest Markdown doctest paths. Check wiki links and anchors separately.
Execute supplemental snippets manually in isolated temporary Python files;
do not claim that ordinary fenced Python blocks are automatically tested.

Existing runnable scripts are covered by
[example integration tests](../../tests/integration/test_examples.py). Keep guide
excerpts consistent with those scripts; label additional wiki-only examples as
supplemental. Confirmed unresolved source defects belong in
[BUGS.md](../../BUGS.md), not documentation backlogs.

Continue with [agent skills](agent-skills.md) or
[integration and releases](releasing.md). Return to [development](README.md).
