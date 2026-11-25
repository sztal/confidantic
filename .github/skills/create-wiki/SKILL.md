---
name: create-wiki
description: Create verified concept, architecture, API, or tutorial pages within the existing wiki structure.
argument-hint: Topic, audience, and relevant sources or decisions
---

# Create Wiki Pages

Create concise Markdown documentation for the requested topic and audience.
Inspect relevant source, tests, configuration, agent guidance, and related pages
before asserting facts. Use `src/confidantic/`, `tests/`, `docs/`, and `examples/` as
project evidence. Distinguish verified facts from assumptions and open questions.

## Structure and scope

Preserve the existing handbook organization:

- `wiki/`: handbook overview and navigation.
- `wiki/concepts/`: observable behavior and package concepts.
- `wiki/architecture/`: design and developer implementation notes.
- `wiki/api/`: references mirroring the package modules.
- `wiki/examples/`: practical guides linked to runnable scripts in `examples/`.

Create only pages needed for the request. Use descriptive lowercase, hyphenated
filenames, preserve related navigation, and link to local evidence. Avoid copying
large source excerpts. Use tables or diagrams only when they clarify the topic.
For workflow notes, follow the existing ancestry-preserving merge helper and
[release guide](../../../docs/releasing.md). Notes are consolidated at integration
into `master`; Towncrier assembles them during release preparation.

## Examples and validation

Preserve existing runnable guides and smoke coverage in
`tests/integration/test_examples.py`. Wiki Markdown is not in the default pytest
or documentation-build paths. Do not claim ordinary fenced code is tested by
pytest's doctest support.

When creating executable examples, normally ask whether to configure their
validation unless the user already specified it. If authorized, prefer extending
the existing runnable-script and smoke-test approach. Configure wiki doctest
discovery only when explicitly needed, preserving existing discovery and using
examples the runner actually executes. Verify representative collection and
execution. If setup is declined or unavailable, leave it unchanged and report
the limitation.

Verify facts, links, and Markdown. Run Nox lint before any pytest checks for
approved example changes, plus applicable documentation checks. Report failures
or unavailable checks. Keep changes within `wiki/`, except for an authorized
example-testing setup. Never use wiki pages as a bug backlog or session log;
report confirmed defects for [BUGS.md](../../../BUGS.md).
