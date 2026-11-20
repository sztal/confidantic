# Use repository agent skills

Choose the skill that matches the requested action and read its `SKILL.md` before
starting. A task can move from investigation to implementation, but the requested
scope must change explicitly. The skills are instructions for repository work;
the Make helpers execute integration and release operations.

| Task                           | Skill                                                                                                                                    | Scope                                                                           |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Investigate behavior           | [investigate](../../.github/skills/investigate/SKILL.md)                                                                                 | Inspect and reproduce; only `BUGS.md` may change                                |
| Fix confirmed defects          | [fix-bugs](../../.github/skills/fix-bugs/SKILL.md)                                                                                       | Fix behavior, add regression coverage, validate, and update the ledger          |
| Audit tests                    | [test-audit](../../.github/skills/test-audit/SKILL.md), [test-coverage-audit](../../.github/skills/test-coverage-audit/SKILL.md)         | Follow the audit scope; record confirmed source defects rather than fixing them |
| Create or revise wiki pages    | [create-wiki](../../.github/skills/create-wiki/SKILL.md), [update-wiki](../../.github/skills/update-wiki/SKILL.md)                       | Verify claims and preserve the handbook structure and runnable-guide links      |
| Refresh project entry points   | [update-readme](../../.github/skills/update-readme/SKILL.md), [agent-context-update](../../.github/skills/agent-context-update/SKILL.md) | Keep README and agent guidance aligned with verified behavior                   |
| Prepare or perform integration | [merge-branch](../../.github/skills/merge-branch/SKILL.md), [merge-to-master](../../.github/skills/merge-to-master/SKILL.md)             | Use the existing isolated merge helper and consolidated notes                   |
| Build and inspect artifacts    | [build-package](../../.github/skills/build-package/SKILL.md)                                                                             | Build and check distributions without inferring publication authority           |
| Prepare or publish a release   | [release-package](../../.github/skills/release-package/SKILL.md)                                                                         | Select the explicitly requested release stage and version                       |

## Investigation and the defect ledger

Investigation leaves source, tests, configuration, and documentation read-only.
Record confirmed unresolved source bugs only in [BUGS.md](../../BUGS.md), with
source file and line, symptom, minimal reproduction or evidence, affected
behavior, and expected behavior. Verify stale entries before removing them;
never delete the ledger. A fix removes its entry only after regression tests and
required checks pass. Wiki pages explain durable behavior, not task progress or
bug backlogs.

## Merge and release boundaries

A merge review uses `make merge-check`; an authorized integration uses
`make merge`. Both follow the same ancestry-preserving workflow, not squash
merging. The integration step consolidates final user-visible changes into
Towncrier fragments; ordinary coding does not add fragments. Documentation-only
or internal changes use an explicit no-notes reason.

Review does not imply merge permission. Merge does not imply pushing or tagging.
Local release preparation does not imply publishing. Respect the scope already
authorized by the user; do not ask again for actions already included in it.
See [merging and releasing](releasing.md) for commands and the separate stages.

Return to [development](README.md).
