______________________________________________________________________

## name: create-wiki description: "Create concise repository wiki pages from a user-supplied topic. Use when asked to add, document, capture, or update a wiki note, design note, decision record, investigation summary, or technical reference under wiki/." argument-hint: "Topic and any relevant source files, decisions, or validation results"

# Create Wiki Pages

Create brief, informative Markdown notes for this repository. Derive the page
topic and scope from the user's request; ask one focused question only when the
topic or intended audience is not clear enough to write a useful note.

## Workflow

1. Read [wiki/example.md](../../../wiki/example.md) and the source files most
   directly relevant to the requested topic.
1. Identify the note's purpose, intended reader, key decisions or facts, and
   any validation or follow-up work worth recording.
1. Choose a concise, descriptive lowercase filename using hyphens. Create the
   page only in `wiki/` or one of its subdirectories. Never create wiki content
   elsewhere in the repository.
1. Write a short GitHub-flavored Markdown page. Use the example structure when
   it fits: `Goal`, `Decisions and findings`, `Validation`, and `Follow-up`.
   Omit empty sections and add focused headings when the topic calls for them.
1. Prefer plain prose and lists. Include links to relevant local files when
   useful. Use tables, Mermaid diagrams, reference-style links, or math only
   when they materially improve clarity; do not add them as decoration.
1. Verify the file is valid Markdown, concise, factually supported by the
   supplied context or inspected sources, and located under `wiki/`.

## Quality Bar

- Capture the topic and the information a future contributor needs to act on.
- Distinguish confirmed facts from assumptions, open questions, and follow-up.
- Avoid copying large source excerpts, changelog entries, or implementation
  narration.
- Use ASCII unless the subject requires other characters.
- Do not modify production code, tests, or documentation outside `wiki/` as
  part of this skill.
