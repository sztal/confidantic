---
name: merge-to-master
description: Prepare or complete a local feature/development branch merge into master with consolidated Towncrier notes and validation. Use for merge requests, not ordinary development or individual bug fixes.
---

# Merge to master

Read [the release guide](../../../docs/releasing.md). Use the existing Make
commands; do not implement an alternative Git merge procedure.

Inspect the source branch and current local and remote `master` before writing
notes. Summarize the final integrated user-visible behavior, including migrations,
using source, tests, and documentation as evidence. Account for changes already
on master; do not turn intermediate commits or abandoned APIs into release notes.
Resolve conflicts as a separate source-branch change before retrying preparation.

Write category files (`added.md`, `changed.md`, `fixed.md`, `removed.md`,
`deprecated.md`, `security.md`) in a temporary directory outside the repository.
Only include categories with relevant changes. For documentation-only or internal
work, use `NO_NOTES_REASON` with a concise explanation instead. Ordinary coding
work does not create fragments; the merge helper writes them during integration.

Start from a clean checkout on `master` that contains the current remote master.
Use `make merge-check BRANCH=feature NOTES=/path/to/notes` when the request is
only to prepare or review. When the user has requested the merge, run
`make merge BRANCH=feature NOTES=/path/to/notes`; it performs the checks itself,
so a separate rehearsal is unnecessary. Substitute `NO_NOTES_REASON='reason'`
for `NOTES` when applicable. Respect existing authorization; a review request
does not authorize merging. Neither command pushes or creates a release tag.

On failure, report the retained preparation checkout and the cause. Resolve the
cause before retrying; do not reset user work, force-update master, or bypass
validation. Report the resulting master commit and summaries after a merge.
