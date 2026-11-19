# Use agent workflows

Repository skills describe how to perform a task within Confidantic's working
conventions. Select a skill by the requested action and read its `SKILL.md`.
Start with [contributor setup and checks](contributing.md).

| Task                            | Repository skill                                                                                                                                                                                                               | Expected outcome                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Investigate behavior            | [investigate](https://github.com/sztal/confidantic/blob/master/.github/skills/investigate/SKILL.md)                                                                                                                            | Evidence and recommendations; confirmed source defects recorded in `BUGS.md` |
| Fix confirmed bugs              | [fix-bugs](https://github.com/sztal/confidantic/blob/master/.github/skills/fix-bugs/SKILL.md)                                                                                                                                  | Focused fixes, regression tests, validation, and ledger updates              |
| Review tests and coverage       | [test-audit](https://github.com/sztal/confidantic/blob/master/.github/skills/test-audit/SKILL.md), [test-coverage-audit](https://github.com/sztal/confidantic/blob/master/.github/skills/test-coverage-audit/SKILL.md)         | Follow the audit scope and record source defects without fixing them         |
| Maintain wiki pages             | [create-wiki](https://github.com/sztal/confidantic/blob/master/.github/skills/create-wiki/SKILL.md), [update-wiki](https://github.com/sztal/confidantic/blob/master/.github/skills/update-wiki/SKILL.md)                       | Verified handbook pages within the existing structure                        |
| Refresh project entry points    | [update-readme](https://github.com/sztal/confidantic/blob/master/.github/skills/update-readme/SKILL.md), [agent-context-update](https://github.com/sztal/confidantic/blob/master/.github/skills/agent-context-update/SKILL.md) | README and agent instructions aligned with current behavior                  |
| Prepare or integrate a branch   | [merge-branch](https://github.com/sztal/confidantic/blob/master/.github/skills/merge-branch/SKILL.md), [merge-to-master](https://github.com/sztal/confidantic/blob/master/.github/skills/merge-to-master/SKILL.md)             | Existing isolated merge helper with consolidated notes                       |
| Build and inspect distributions | [build-package](https://github.com/sztal/confidantic/blob/master/.github/skills/build-package/SKILL.md)                                                                                                                        | Checked artifacts                                                            |
| Prepare or publish a version    | [release-package](https://github.com/sztal/confidantic/blob/master/.github/skills/release-package/SKILL.md)                                                                                                                    | The explicitly requested release stage and version                           |

## Investigation and implementation have different scopes

Investigation keeps source, tests, configuration, and documentation read-only;
only [BUGS.md](https://github.com/sztal/confidantic/blob/master/BUGS.md) may change.
Record confirmed unresolved source defects there with source file and line,
symptom, minimal reproduction or evidence, affected behavior, and expected
behavior. Do not use wiki pages as a bug backlog or session log.

Moving from investigation to implementation requires an explicit change of task
scope. After a fix, remove the ledger entry only when regression tests and
required checks pass. Never delete the ledger itself.

## Choose the integration or release stage

| Requested action    | Command                                              | Boundary                                                    |
| ------------------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| Review integration  | `make merge-check`                                   | Rehearse in isolation; do not advance master                |
| Integrate a branch  | `make merge`                                         | Validate and advance local master; do not push or tag       |
| Rehearse a release  | `uv run python -m scripts.release --dry-run VERSION` | Use independent refs; leave caller files and refs unchanged |
| Prepare a release   | `make release VERSION=...`                           | Create local release state and an annotated tag             |
| Push prepared state | Exact atomic push command printed by preparation     | Update the remote; tag pushes do not publish packages       |
| Publish             | `make publish TAG=...`                               | Dispatch and track the publishing workflow                  |

Merge commands need `BRANCH` and either `NOTES` or `NO_NOTES_REASON`; the table
identifies stages rather than complete command invocations. Follow
[merging and releasing](releasing.md) for prerequisites, complete commands,
publisher setup, and recovery. Use the existing ancestry-preserving helper,
not squash merging. Ordinary development adds no fragments; integration creates
consolidated Towncrier notes, and final release preparation assembles them.
Documentation-only and internal integrations record a no-notes reason.

Review does not authorize integration, and local preparation does not authorize
pushes or publication. Honor the scope already requested by the user without
asking again for actions it includes. See the
[wiki skill guide](https://github.com/sztal/confidantic/blob/master/wiki/dev/agent-skills.md)
for further repository guidance.
