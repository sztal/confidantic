---
name: test-coverage-audit
description: Find meaningful missing pytest coverage and add focused tests.
argument-hint: Optional module or coverage concern
---

# Test Coverage Audit

Run `uv run noxfile.py -s lint` before collecting coverage, then use fresh data:

```console
coverage_dir=$(mktemp -d)
COVERAGE_FILE="$coverage_dir/.coverage" make coverage
```

Inspect uncovered behavior alongside its tests. Report the data path and command;
do not erase another contributor's coverage. A fresh file also avoids stale paths
after package files move or disappear, which can cause `No source for code`.
Prioritize branches, validation, error paths, and public behavior. Avoid adding
tests only to execute trivial lines.

Use `src/confidantic/` as the source package and `tests/` as the behavioral test
surface. Example scripts are under `examples/`; check `tests/integration/test_examples.py`
to see which are covered by smoke tests.

If the audit confirms an unresolved source bug, add a concise entry to
`../../../BUGS.md` with its source file and line, concise symptom, minimal reproduction or
evidence, affected behavior, and expected behavior. Do not fix it during a coverage audit and
never track it in `wiki/`.

Run `uv run noxfile.py -s lint` before `uv run pytest` after test changes;
pre-commit can modify files. Pytest collects `src/confidantic/`, `tests/`, `docs/`,
and `README.md`. Reserve `make nox`, `nox -s tests`, or
`uv run noxfile.py -s tests` for humans; `make test` runs direct pytest.

Create the ledger if missing and remove entries proven stale or already fixed;
never delete `BUGS.md`, even when empty. Report unavailable or failing checks.
