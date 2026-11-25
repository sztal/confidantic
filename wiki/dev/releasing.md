# Merge changes and release a version

The [release guide](../../docs/releasing.md) is authoritative for prerequisites,
publisher setup, CI behavior, and recovery. This page maps the normal contributor
workflow to its commands. Examples use placeholder branch names and versions;
choose the intended branch and an advancing version before running them.

## Integrate a development branch

Develop on a dedicated branch without adding Towncrier fragments. At integration,
summarize the final user-visible difference from current master, excluding
abandoned APIs, intermediate fixes to unreleased work, and already-integrated
changes. The [merge skill](../../.github/skills/merge-to-master/SKILL.md) guides
this review.

Write nonempty category files outside the checkout, such as
`/tmp/merge-notes/added.md` and `/tmp/merge-notes/fixed.md`. Categories come from
Towncrier configuration: added, changed, fixed, removed, deprecated, security.
Fetch remote state and start from clean `master` containing current
`origin/master`:

```console
git fetch origin --tags
git switch master
make merge-check BRANCH=my-feature NOTES=/tmp/merge-notes
make merge BRANCH=my-feature NOTES=/tmp/merge-notes
```

The rehearsal is optional: `merge` validates itself. For documentation-only work,
replace `NOTES=...` with `NO_NOTES_REASON='Documentation only'` on either command.
Use an appropriate reason for other internal-only changes.

The helper prepares an independent temporary checkout, merges with
`--no-ff --no-commit`, and writes one fragment per relevant category. It validates
and commits the integrated result before advancing local master, rechecking
source and target refs. It preserves ancestry, detects already-merged branches,
and does not push or tag. Resolve conflicts on the development branch and retry;
do not replace the helper with a squash merge or bypass validation.

## Prepare a release locally

Versions come from annotated Git tags through Hatchling and `hatch-vcs`;
lightweight tags are ignored. Never edit a static version field. Use canonical
`X.Y.Z`, optionally followed by `aN`, `bN`, or `rcN`, advancing existing local and
remote release tags. On clean master containing remote master:

```console
make release-notes VERSION=1.2.0
uv run python -m scripts.release --dry-run 1.2.0
make release VERSION=1.2.0
```

These are preview, rehearsal, and actual local preparation stages. The rehearsal
uses independent refs and leaves caller files and refs unchanged. Final releases
assemble and commit Towncrier notes and consume fragments; candidates retain
pending fragments. Preparation creates the annotated tag before building and
checking distributions so artifact versions must match it exactly.

For artifact inspection independently, use `make build` and `make check-dist`.
`make check` includes the shared validation pipeline. See
[contributing](contributing.md#validate-in-order) for check order and policy.

## Push and publish explicitly

Local preparation prints an atomic push command. When pushing is requested, use
that exact command, with fully qualified refs; for example:

```console
git push --atomic origin refs/heads/master:refs/heads/master refs/tags/v1.2.0:refs/tags/v1.2.0
```

Pushing a tag validates it but does not publish a package or create a GitHub
release. After the annotated tag and its commit exist on remote master history,
request publication separately:

```console
make publish TAG=v1.2.0
```

Final versions publish to PyPI; candidates such as `v1.2.0rc1` publish exclusively
to TestPyPI. GitHub CLI authentication and the corresponding Trusted Publisher
setup are required. The helper dispatches `release.yaml` from master and waits
for its specific run. That workflow validates the tagged commit, builds fresh
artifacts, publishes those artifacts, and then creates the GitHub release.
It does not upload a developer's local `dist/`.

## Recover without changing published history

Failed local preparation retains a checkout and reports its path. Inspect that
checkout before cleanup. A publishing timeout can mean the workflow is still
running; find its request ID before retrying. Never move or recreate a release
tag to hide a failure or blindly retry a partial upload.

If upload succeeded but GitHub release creation or documentation deployment
failed, repair the failed stage without repeating publication. Follow the
[recovery procedure](../../docs/releasing.md#recovery) for the exact situation.
Return to [development](README.md).
