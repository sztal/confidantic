______________________________________________________________________

## name: update-wiki description: "Update existing repository wiki pages from user-supplied changes. Use when asked to revise, correct, refresh, expand, clarify, or maintain a Markdown page under wiki/ while keeping it accurate in the context of the project codebase." argument-hint: "Wiki page, requested update, and any relevant source files or decisions"

# Update Wiki Pages

Update existing Markdown pages under `wiki/` from the user's input. Preserve
the page's useful structure and concise style while making the requested
information accurate, coherent, and actionable for future contributors.

## Workflow

1. Read the target wiki page, [wiki/example.md](../../../wiki/example.md), and
   the project files most directly relevant to the requested update.
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
- Distinguish verified facts from assumptions, questions, and pending work.
- Do not add decorative advanced Markdown features or copy large source
  excerpts.
- Do not modify files outside `wiki/` as part of this skill.
