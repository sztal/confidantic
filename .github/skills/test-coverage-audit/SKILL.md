---
name: test-coverage-audit
description: Find meaningful missing pytest coverage and add focused tests.
argument-hint: Optional module or coverage concern
---

# Test Coverage Audit

Start with `uv run coverage erase && make coverage`, then inspect uncovered
behavior alongside its tests. The explicit erase is needed because the Make
target uses the persistent repository `.coverage` file; after package files
are moved or deleted, stale paths can make `coverage report` fail with
`No source for code`.
Prioritize branches, validation, error paths, and public behavior. Avoid adding
tests only to execute trivial lines.

Use `confidantic/` as the source package and `tests/` as the behavioral test
surface. Example scripts are under `examples/`; check `tests/test_examples.py`
to see which are covered by smoke tests.

If the audit confirms an unresolved source bug, add a concise entry to
`../../../BUGS.md` with its symptom, reproduction or evidence, affected
behavior, and expected behavior. Do not fix it during a coverage audit and
never track it in `wiki/`.

Run `uv run noxfile.py -s lint` before `uv run pytest` after test changes;
pre-commit can modify files. Pytest collects `confidantic/`, `tests/`, `docs/`,
and `README.md`. Never run `make test`, `nox -s tests`, or
`uv run noxfile.py -s tests`.
