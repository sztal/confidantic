---
name: docstring-audit
description: Audit public documentation and doctest examples for accuracy.
argument-hint: Optional module or documentation concern
---

# Docstring Audit

Check public classes, functions, and properties for concise accurate
Docstrings. Review examples for runnable doctests and run `uv run pytest` after
documentation changes. Run `uv run noxfile.py -s lint` before completion. Keep
comments focused on non-obvious behavior and avoid documenting implementation
details as API contracts.

Record any confirmed unresolved source defect in `../../../BUGS.md`, not in
`wiki/`, and leave its fix to a separate bug-fixing task. Never run `make test`,
`nox -s tests`, or `uv run noxfile.py -s tests`.
