---
name: investigate
description: Investigate a reported behavior without changing existing source files.
argument-hint: Describe the issue, command, failure, or behavior
---

# Investigate

Start from the nearest failing test, command, symbol, or file. Reproduce the
behavior when possible, identify the controlling code path, and report facts,
hypotheses, evidence, and a minimal fix direction. Do not modify existing
source, tests, configuration, or documentation files during investigation.

Use `uv run pytest` for a focused reproduction. The test suite also collects
doctests from `confidantic/`, `docs/`, and `README.md`; examples are executable
scripts under `examples/`, while `tests/test_examples.py` smoke-tests a
selected subset of them.

Do not use `wiki/` as a bug tracker. Because this workflow is read-only, report
confirmed unresolved defects for a follow-up task to record in
`../../../BUGS.md`.
