---
name: build-package
description: Build and verify Confidantic source distributions and wheels without creating a release or publishing.
argument-hint: Optional artifact, version, or build concern
---

# Build Package

Read [the release guide](../../../docs/releasing.md), `pyproject.toml`, build
scripts, and CI configuration. Verify the distribution/import names, package
layout, supported Python versions, backend, version source, and expected files.
Confidantic uses Hatchling with annotated Git tags as its version source.
Inspect Git state and available tags; report development versions accurately.
Building does not authorize tags, merges, pushes, releases, or publication.

Use `make build` and `make check-dist`. The build helper builds fresh artifacts
outside the repository and replaces `dist/` only after a successful build.
Report that replacement behavior; do not manually delete old artifacts.

Inspect wheel and sdist metadata for name, version, Python requirements, license,
and expected package files including `py.typed`; check entry points if present.
The distribution checker validates the exact artifact pair, installs the wheel
with each optional-dependency profile, and rebuilds and installs the sdist outside
Git. Preserve those checks rather than treating a successful build as sufficient.

Run applicable checks, with Nox lint before any pytest invocation. Report commands,
artifact paths, versions, results, and limitations. For release work follow
[release-package](../release-package/SKILL.md); use `TAG=vX.Y.Z` with
`make check-dist` only for an annotated tag at the checked-out commit. Do not
create or move tags or override versions to make a development build look released.
