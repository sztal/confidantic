---
name: agent-context-update
description: Audit the repository and update AGENTS.md and all skills to match verified project facts.
argument-hint: Optional focus area; default is AGENTS.md and every skill
---

# Agent Context Update

Use this skill when repository structure, architecture, tools, or workflows
change and agent guidance may be stale. Read [the agent guide](../../../AGENTS.md).

1. Inspect the repository tree, package exports, tests, `README.md`,
   `pyproject.toml`, `Makefile`, `noxfile.py`, `zensical.toml`, `.python-version`,
   maintenance scripts, and CI/release configuration.
1. Verify project facts rather than copying template defaults. `src/confidantic/`
   is the package; `docs/`, `examples/`, and `changelog.d/` are the published
   documentation, runnable guides, and release-note surfaces. Test placement
   follows `tests/README.md`; example coverage is listed in
   `tests/integration/test_examples.py`.
1. Update `AGENTS.md` and every skill under `.github/skills/`, preserving
   project-specific behavior and removing unsupported or stale claims.
1. Keep the existing merge helper, annotated-tag versions, release-note timing,
   and explicit publication boundaries. The `merge-branch` skill delegates to
   `merge-to-master`; `build-package` and `release-package` cover separate stages.
1. Verify type-checking guidance against `[tool.project-checks]` and its Make,
   Nox, shared validation, and CI callers. Basic checking is source-only and
   required by default. `make typecheck` propagates errors; `make check-typecheck`
   applies the required/advisory policy.
1. Retain `BUGS.md` as the sole defect ledger and preserve the existing wiki
   structure. Report misplaced backlog content for a separate migration;
   do not silently broaden a context update into record maintenance.
1. Run Nox lint before direct pytest, plus applicable typecheck and docs checks.
   Report failures or unavailable checks; do not leave permanent claims that
   checks are currently passing. Re-read all guidance for agreement.

Keep later updates limited to agent guidance unless the user explicitly requests
related tooling or documentation changes. Do not change package behavior.
The package supports Python 3.13 and later; read the development interpreter
from `.python-version` (currently 3.15). Use `uv sync --group dev` and add the
`docs` group for documentation work.

`make test` runs direct pytest. Agents may use it or `uv run pytest` after lint.
Reserve `make nox`, `nox -s tests`, and `uv run noxfile.py -s tests` for humans.
Use a temporary `COVERAGE_FILE` only when coverage statistics are needed.
