______________________________________________________________________

## name: agent-context-update description: Audit the repository and update AGENTS.md and all generated skills so they match the current project. argument-hint: Optional focus area; default is AGENTS.md and every skill

# Agent Context Update

Use this skill when the repository structure, architecture, tools, or workflows
have changed and agent guidance may be stale.

## First run in a newly generated repository

1. Inspect the complete repository tree and the selected package layout.
1. Read `pyproject.toml`, `README.md`, `Makefile`, `noxfile.py`, and tests.
1. Replace every placeholder in `AGENTS.md` with verified project facts.
1. Update every skill under `.github/skills/` with the actual paths, commands,
   environment rules, and testing conventions.
1. Remove assumptions that are not supported by the source tree.
1. Run `make lint`, `make test`, and the relevant Nox sessions.
1. Re-read all agent files and confirm they agree with each other.

## Later updates

Keep edits limited to agent guidance. Verify claims against source code and
current commands before documenting them. Do not change runtime behavior.
