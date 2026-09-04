---
name: fix-bugs
description: Fix confirmed bugs with focused regression tests.
argument-hint: Optional bug or module to fix
---

# Fix Bugs

Read `../../../BUGS.md` when fixing a tracked defect. Confirm the bug against
current source, make the smallest focused change, and add a regression test that
fails before the fix. Do not mix unrelated refactors or test-audit work into a
bug fix.

Source code lives under `confidantic/` and focused regression tests belong under
`tests/`. Add a Towncrier fragment under `changelog.d/` for user-visible bug
fixes.

Run `uv run noxfile.py -s lint` before `uv run pytest`; pre-commit can modify
files. Use `make coverage` only when coverage statistics are relevant. After
the fix and required checks pass, remove its entry from `../../../BUGS.md`; Git
history retains the resolved record. Never track bugs in `wiki/`.

Never run `make test`, `nox -s tests`, or `uv run noxfile.py -s tests`; the full
multi-version Nox matrix is reserved for a human contributor.
