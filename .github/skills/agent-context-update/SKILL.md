---
name: agent-context-update
description: Audit the repository and update AGENTS.md and all generated skills to match the current project.
argument-hint: Optional focus area; default is AGENTS.md and every skill
---

# Agent Context Update

Use this skill when the repository structure, architecture, tools, or workflows
have changed and agent guidance may be stale.

## First run in a newly generated repository

1. Inspect the complete repository tree and the selected package layout.
1. Read `pyproject.toml`, `README.md`, `Makefile`, `noxfile.py`,
   `zensical.toml`, `.python-version`, and tests.
   `confidantic/` is the import package; `docs/`, `examples/`, and
   `changelog.d/` are the documentation, runnable-guide, and release-note
   surfaces. `tests/test_examples.py` covers a selected subset of the scripts
   under `examples/`, not necessarily every script.
1. Replace every placeholder in `AGENTS.md` with verified project facts.
1. Update every skill under `.github/skills/` with the actual paths, commands,
   environment rules, and testing conventions.
1. Keep confirmed unresolved source defects in root `BUGS.md` and remove any
   bug-backlog content from `wiki/`.
1. Remove assumptions that are not supported by the source tree.
1. Run `uv run noxfile.py -s lint` before `uv run pytest`; pre-commit can
   modify files. Use `make coverage` only when coverage statistics are
   relevant.
1. Re-read all agent files and confirm they agree with each other.

Never run `make test`, `nox -s tests`, or `uv run noxfile.py -s tests` as an
agent. The Nox `tests` session runs the full supported-Python matrix; that
multi-version run is reserved for a human contributor. Use the direct pytest
command for the repository test suite:

```console
uv run pytest
```

## Later updates

Keep edits limited to agent guidance and project records such as `BUGS.md` or
wiki migrations. Verify claims against source code and current commands before
documenting them. Do not change runtime behavior.

The package supports Python 3.11 and later. The repository default is recorded
in `.python-version` and is currently Python 3.13. Use `uv sync --group dev`
to install the development toolchain and add `--group docs` for documentation
builds.
