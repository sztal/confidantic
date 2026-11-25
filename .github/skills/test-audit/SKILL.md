---
name: test-audit
description: Audit pytest coverage and quality against the package source.
argument-hint: Optional module or test concern
---

# Test Audit

Review public behavior, error paths, and meaningful edge cases. Prefer shared
fixtures, factory helpers, parametrization, and short behavioral assertions.
Do not test trivial implementation details. Treat disagreement with current code
as a potentially stale test until stronger evidence confirms a source defect.

If the audit confirms an unresolved source bug, add a concise entry to
`../../../BUGS.md` with its source file and line, concise symptom, minimal reproduction or
evidence, affected behavior, and expected behavior. Do not fix source bugs during a test audit and
never track them in `wiki/`.

Package behavior is implemented under `src/confidantic/`, with tests under
`tests/`; runnable examples are under `examples/`. Check
`tests/integration/test_examples.py` for the smoke-tested scripts.

Run `uv run noxfile.py -s lint` before `uv run pytest` after test changes;
pre-commit can modify files. Use `make coverage` with a temporary `COVERAGE_FILE`
only when statistics are relevant; preserve existing coverage data. Pytest collects `src/confidantic/`, `tests/`, `docs/`, and `README.md`.
Reserve `make nox`, `nox -s tests`, or `uv run noxfile.py -s tests` for humans; `make test` runs direct pytest.

Create the ledger if missing and remove entries proven stale or already fixed;
never delete `BUGS.md`, even when empty. Report unavailable or failing checks.
