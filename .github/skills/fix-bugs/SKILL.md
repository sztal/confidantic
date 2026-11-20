---
name: fix-bugs
description: Fix confirmed bugs with focused regression tests and maintain BUGS.md.
argument-hint: Optional bug entry or module to fix
---

# Fix Bugs

Read [BUGS.md](../../../BUGS.md) and confirm each selected defect against current
source before changing code. Resolve entries one at a time. Remove entries
proven stale or already fixed rather than restoring obsolete behavior.

Make the smallest focused source change and add a regression test that fails
before the fix and passes afterward. Source lives under `confidantic/`; place
regressions according to `tests/README.md`. Do not mix unrelated refactors or
test-audit work into a fix. Release notes are consolidated when merging into
`master`; do not create fragments during individual fixes.

Run `uv run noxfile.py -s lint` before focused `uv run pytest` and any other
required checks. After validation passes, remove the resolved entry. Never delete
`BUGS.md`, even when empty, and never track defects in the wiki. Report unavailable
or failing checks. Use a temporary `COVERAGE_FILE` only when statistics are useful.

`make test` runs direct pytest. Reserve `make nox`, `nox -s tests`, and
`uv run noxfile.py -s tests` for human contributors.
