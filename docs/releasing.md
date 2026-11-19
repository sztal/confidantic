# Merging and releasing

Confidantic uses `master` for integration and annotated Git tags for package
versions. Hatchling and `uv-dynamic-versioning` derive the version; there is no
version field to bump. `confidantic.__version__` reads installed package metadata.

## Development and merge notes

Develop features and fixes without adding changelog fragments. When a branch is
ready to merge, summarize the final changes relative to the integrated master.
The `merge-to-master` skill can write these summaries. Exclude abandoned APIs,
intermediate fixes to unreleased features, and changes already on master.

Put nonempty category files in a directory outside the checkout, for example
`/tmp/merge-notes/added.md` and `/tmp/merge-notes/fixed.md`. Supported categories
come from the Towncrier configuration: added, changed, fixed, removed, deprecated,
and security. Start on clean `master` containing the current `origin/master`:

```console
git fetch origin --tags
git switch master
make merge-check BRANCH=my-feature NOTES=/tmp/merge-notes
make merge BRANCH=my-feature NOTES=/tmp/merge-notes
```

The rehearsal is optional: `merge` performs validation itself. For internal or
documentation-only changes, replace `NOTES` with
`NO_NOTES_REASON='Documentation only'`. Merge commands do not push or create tags.

Preparation uses an independent temporary Git checkout. It merges with
`--no-ff --no-commit`, writes one fragment per category using the source commit
identifier, validates the integrated result, and commits it. Local master advances
only after validation and a fresh check of the source and target references.
Already-merged branches produce no duplicate notes. Resolve merge conflicts on
the feature branch before retrying; failed preparation checkouts are retained.

## Build and check

Install the toolchain with `uv sync --group dev --group docs`.

```console
make build
make check-dist
make check
```

`build` replaces `dist/` after a successful fresh `uv build --no-sources`.
`check-dist` requires exactly one wheel and one sdist, checks their metadata and
contents with Twine, tests the supplied wheel with each optional dependency
profile, and rebuilds and installs the sdist outside Git. `TAG=v1.2.0` additionally
requires an annotated tag at the current commit and matching artifact versions.
Development versions are allowed only when no release tag is requested.

`check` runs Nox lint before direct pytest, followed by `make check-typecheck`,
docs, build, and distribution checks. It never invokes the local multi-Python Nox matrix.
Checks that rewrite files fail preparation so the changes can be reviewed.

### Type-checking policy

The `[tool.project-checks]` table in `pyproject.toml` configures the same policy
for local checks, CI, merge preparation, and release preparation:

```toml
[tool.project-checks]
typecheck_level = "basic"
typecheck_source_only = true
require_typecheck = true
```

`basic` uses non-strict mypy with the existing explicit diagnostics in
`[tool.mypy]`. `strict` additionally enables strict checks; `none` skips mypy.
Source-only checking targets `confidantic/`. Setting `typecheck_source_only`
to false explicitly includes `tests/`, `scripts/`, and `noxfile.py`.

`make typecheck` runs the configured level and scope and propagates errors even
when `require_typecheck` is false. `make check-typecheck` applies that setting:
errors block validation by default; setting it to false reports failures as
advisory and continues. Invalid settings always fail. `_typecheck` is the internal
Nox execution target. Direct `uv run noxfile.py -s typecheck` also uses the shared
level and scope and propagates errors; explicit Nox positional arguments can
override the target paths. Both direct and policy-aware commands skip mypy when
disabled. These settings do not change pytest strictness or strict docs builds.

## Build and publish documentation

```console
make docs
make docs-serve
```

`docs` runs the clean, strict Nox documentation build and writes `site/`.
`docs-serve` opens the local preview with automatic reload. Neither command
publishes the site.

CI validates documentation on pull requests, master pushes, and release runs.
After successful checks on a master push, it deploys that commit's documentation
to GitHub Pages. Successful final PyPI publication also deploys documentation,
using the exact commit resolved from the published tag. TestPyPI candidates and
tag pushes still validate documentation but do not trigger a release deployment.
Later master pushes can update the site again; this is a single current site,
not a versioned documentation archive.

Both deployment paths use the shared Pages workflow. It installs locked
documentation dependencies and all package extras, builds strictly, then adds
the coverage report and badge from the same run's validation artifact. Deployments
share a concurrency group so they do not run simultaneously.

In the repository's **Settings → Pages**, select **GitHub Actions** as the
publishing source. The `github-pages` environment must allow deployments from
`master`, including release workflows dispatched there. The workflow supplies
the required `pages: write` and `id-token: write` permissions. See
[GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Prepare a release locally

Use canonical `X.Y.Z` versions, optionally followed by `aN`, `bN`, or `rcN`.
Versions must advance existing local and remote release tags. Development and
local-version suffixes are not accepted for publication.

```console
make release-notes VERSION=1.2.0
uv run python -m scripts.release --dry-run 1.2.0
make release VERSION=1.2.0
```

Preparation requires clean `master` containing remote master. The dry run uses
independent Git refs and leaves caller files, branches, and tags unchanged.
For candidates, pending fragments remain intact. For final releases, Towncrier
writes and commits the versioned changelog and consumes those fragments. The
annotated `v1.2.0` tag is created before building and checking its distributions.
No version override is used. Package versions must match the tag exactly.

The command keeps the release local and prints an explicit push command:

```console
git push --atomic origin refs/heads/master:refs/heads/master refs/tags/v1.2.0:refs/tags/v1.2.0
```

Use full refs because a branch and tag can have the same name. Pushing a tag runs
validation only. It does not publish packages or create a GitHub release.

## Publish explicitly

After the annotated tag and its commit exist on remote master history:

```console
make publish TAG=v1.2.0rc1
make publish TAG=v1.2.0
```

These are separate examples: candidates publish exclusively to TestPyPI; final
versions publish exclusively to PyPI. GitHub CLI authentication is required.
The command dispatches `release.yaml` from `master` with the requested tag and a
unique request ID, prints its run URL, and waits for that specific workflow.

The workflow resolves the remote annotated tag, verifies master ancestry, and
validates that exact commit. It builds and checks fresh artifacts in that run,
then uploads those same files with the PyPA action and attestations. It never
uploads a developer's local `dist/`. The corresponding GitHub release is created
only after package publication succeeds; candidates are marked as prereleases.

## Trusted Publisher setup

Configure the publisher separately on PyPI and TestPyPI. For both registrations,
use owner `sztal`, repository `confidantic`, and workflow filename `release.yaml`.
Use environment `pypi` on PyPI and `testpypi` on TestPyPI. Create the corresponding
GitHub repository environments. The workflow uses job-scoped `id-token: write`;
no long-lived PyPI token is needed. If the project does not exist yet, register a
pending publisher. The release workflow must exist on GitHub's default branch,
which must be `master`.

This configuration is an account setup task; adding the workflow does not create
it. See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

## Recovery

Preparation failures print the path to the retained checkout. The original
checkout is preserved until installation of a validated result. Inspect the
retained checkout before deleting it; never reset unrelated work. If the final
local tag import fails after master advances, recover the annotated tag from
that retained checkout after inspecting existing refs; do not overwrite a tag.

A dispatch timeout can mean a workflow is still running. Find the printed request
ID in Actions before retrying. A failed upload can leave some files on the index;
inspect the workflow and index before recovering. Rerun the failed publishing job
with its original retained artifact when appropriate; do not rebuild different
files under an already published version. If package upload succeeded but GitHub
release creation failed, rerun only the failed job. Never delete or move a release
tag to conceal a partial publication. Check publisher registration after an
`invalid-publisher` error.

If documentation deployment fails after a successful package upload, rerun the
failed Pages job in that release workflow while its coverage artifact is retained.
The package is already published; do not repeat the package upload to repair the site.
