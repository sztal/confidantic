---
name: investigate
description: Investigate reported behavior without fixing source files; record confirmed defects in BUGS.md.
argument-hint: Describe the issue, command, failure, or behavior
---

# Investigate

Start from the nearest failing test, command, symbol, or file. Reproduce the
behavior when possible, identify the controlling code path, and report facts,
hypotheses, evidence, and a minimal fix direction.

Do not modify source, tests, configuration, or documentation during investigation.
The sole exception is [BUGS.md](../../../BUGS.md): record confirmed source bugs
there instead of fixing them. Create the ledger if missing. Include the source
file and line, concise symptom, minimal reproduction or evidence, affected
behavior, and expected behavior. Remove entries only when verified stale or
already fixed; never delete the ledger itself. Do not use wiki pages as a backlog
or session log.

Run `uv run noxfile.py -s lint` before focused `uv run pytest` reproductions;
if lint changes files, report that and review the changes before proceeding.
Pytest collects `confidantic/`, `docs/`, `tests/`, and `README.md`.
Check `tests/integration/test_examples.py` for smoke-tested scripts in `examples/`.
Report unavailable or failing checks. `make test` runs direct pytest; the Nox
Python matrix (`make nox` or the `tests` session) is reserved for humans.
