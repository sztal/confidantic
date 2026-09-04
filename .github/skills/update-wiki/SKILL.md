---
name: update-wiki
description: Update durable architecture, design, investigation, or technical reference pages under wiki/.
argument-hint: Wiki page, requested update, and relevant source files or decisions
---

# Update Wiki Pages

Update existing Markdown pages under `wiki/` from the user's input. Preserve
the page's useful structure and concise style while making the requested
information accurate, coherent, and actionable for future contributors.

Never add or retain bug-backlog entries in wiki pages. Confirmed, unresolved
source defects belong only in `../../../BUGS.md`; use a testing or bug-fixing
workflow for those records.

Use `confidantic/` as the package source, `tests/` as the behavioral reference,
`docs/` as the published documentation surface, and `examples/` for runnable
guides. Check `pyproject.toml`, `.python-version`, and `zensical.toml` for
supported Python versions and tool configuration.

## Workflow

1. Read the target wiki page and the project files most directly relevant to
   the requested update.
1. Determine whether the user request adds new facts, corrects stale facts,
   clarifies intent, or changes a decision or follow-up item.
1. Apply the smallest edit that fully reflects the request. Keep content brief,
   retain useful existing context, and remove or revise statements contradicted
   by verified project sources.
1. When the request is ambiguous, prefer an update that keeps the page
   sensible in the context of the codebase: verify names, paths, commands,
   architecture, and behavior against the repository. Preserve uncertainty as
   an open question rather than inventing an unsupported conclusion.
1. Use GitHub-flavored Markdown. Prefer prose and lists; use local links,
   tables, Mermaid diagrams, reference-style links, or math only when they
   materially improve clarity.
1. Verify the resulting page remains valid Markdown, concise, internally
   consistent, supported by the relevant codebase context, and located under
   `wiki/` or one of its subdirectories.

## Quality Bar

- Honor the requested update without rewriting unrelated content.
- Do not leave obsolete paths, commands, APIs, or project claims in the page.
- Remove bug-backlog content after ensuring it is recorded in `BUGS.md`.
- Distinguish verified facts from assumptions, questions, and pending work.
- Do not add decorative advanced Markdown features or copy large source
  excerpts.
- Do not modify files outside `wiki/` as part of this skill.
