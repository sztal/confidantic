---
name: test-coverage-audit
description: Find meaningful missing pytest coverage and add focused tests.
argument-hint: Optional module or coverage concern
---

# Test Coverage Audit

Start with `make coverage`, then inspect uncovered behavior alongside its tests.
Prioritize branches, validation, error paths, and public behavior. Avoid adding
tests only to execute trivial lines.

If the audit confirms an unresolved source bug, add a concise entry to
`../../../BUGS.md` with its symptom, reproduction or evidence, affected
behavior, and expected behavior. Do not fix it during a coverage audit and
never track it in `wiki/`.

Run `uv run pytest` after test changes and `uv run noxfile.py -s lint` before
completion. Never run `make test`, `nox -s tests`, or
`uv run noxfile.py -s tests`.
