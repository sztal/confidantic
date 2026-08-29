---
name: create-wiki
description: Create durable architecture, design, investigation, or technical reference pages under wiki/.
argument-hint: Topic and relevant source files, decisions, or validation results
---

# Create Wiki Pages

Create brief, informative Markdown notes for this repository. Derive the page
topic and scope from the user's request; ask one focused question only when the
topic or intended audience is not clear enough to write a useful note.

Never create a wiki page to track a bug or task-session progress. Confirmed,
unresolved source defects belong only in `../../../BUGS.md`; use a testing or
bug-fixing workflow for those records.

The repository's durable code references are `confidantic/` for the package,
`tests/` for behavior, and `docs/` for published documentation. Verify claims
against those paths and `pyproject.toml` rather than inferring them.

## Workflow

1. Read the existing wiki page closest to the topic, when one exists, and the
   source files most directly relevant to the request.
1. Identify the note's purpose, intended reader, key decisions or facts, and
   any validation or follow-up work worth recording.
1. Choose a concise, descriptive lowercase filename using hyphens. Create the
   page only in `wiki/` or one of its subdirectories. Never create wiki content
   elsewhere in the repository.
1. Write a short GitHub-flavored Markdown page. Use `Goal`, `Decisions and findings`, `Validation`, and `Follow-up` when they fit. Omit empty sections
   and add focused headings when the topic calls for them.
1. Prefer plain prose and lists. Include links to relevant local files when
   useful. Use tables, Mermaid diagrams, reference-style links, or math only
   when they materially improve clarity; do not add them as decoration.
1. Verify the file is valid Markdown, concise, factually supported by the
   supplied context or inspected sources, and located under `wiki/`.

## Quality Bar

- Capture the topic and the information a future contributor needs to act on.
- Distinguish confirmed facts from assumptions, open questions, and follow-up.
- Keep unresolved source defects in `BUGS.md`, never in wiki content.
- Avoid copying large source excerpts, changelog entries, or implementation
  narration.
- Use ASCII unless the subject requires other characters.
- Do not modify production code, tests, or documentation outside `wiki/` as
  part of this skill.
