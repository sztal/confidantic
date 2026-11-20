---
name: docstring-audit
description: Audit public documentation and doctest examples for accuracy.
argument-hint: Optional module or documentation concern
---

# Docstring Audit

Check public classes, functions, and properties for concise, accurate
NumPy-style docstrings. Determine the public API from verified exports and
documentation, not naming conventions alone. Review doctests in `confidantic/`, `docs/`, and
`README.md`, which pytest collects. After documentation changes, run
`uv run noxfile.py -s lint`, `uv run pytest`, and
`uv run noxfile.py -s docs`; lint precedes pytest because pre-commit may modify
files. Keep comments focused on non-obvious behavior and avoid documenting
implementation details as API contracts.

Use `pyproject.toml` and `zensical.toml` as the sources of truth for pytest
collection and API documentation. Public exports include the package root and
the modules listed in `docs/reference/api.md`.

Record any confirmed unresolved source defect in `../../../BUGS.md`, not in
`wiki/`, and leave its fix to a separate bug-fixing task. Include the source file and
line, concise symptom, reproduction, and expected behavior. Create the ledger
if missing, remove only verified stale/fixed entries, and never delete it. Reserve `make nox`,
`nox -s tests`, or `uv run noxfile.py -s tests` for humans; `make test` runs direct pytest.

Report unavailable or failing checks rather than assuming success.
