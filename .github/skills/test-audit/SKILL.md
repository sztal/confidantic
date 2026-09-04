---
name: test-audit
description: Audit pytest coverage and quality against the package source.
argument-hint: Optional module or test concern
---

# Test Audit

Review public behavior, error paths, and meaningful edge cases. Prefer shared
fixtures, factory helpers, parametrization, and short behavioral assertions.
Do not test trivial implementation details.

If the audit confirms an unresolved source bug, add a concise entry to
`../../../BUGS.md` with its symptom, reproduction or evidence, affected
behavior, and expected behavior. Do not fix source bugs during a test audit and
never track them in `wiki/`.

Package behavior is implemented under `confidantic/`, with tests under
`tests/`; runnable examples are under `examples/` and only a selected subset
is smoke-tested by `tests/test_examples.py`.

Run `uv run noxfile.py -s lint` before `uv run pytest` after test changes;
pre-commit can modify files. Use `make coverage` only when coverage statistics
are relevant. Pytest collects `confidantic/`, `tests/`, `docs/`, and `README.md`.
Never run `make test`, `nox -s tests`, or `uv run noxfile.py -s tests`.
