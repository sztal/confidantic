---
name: release-package
description: Build, check, prepare, or explicitly publish Confidantic releases derived from annotated Git tags. Use for package release work; implementation and review requests do not authorize real tags, pushes, or uploads.
---

# Release package

Read [the release guide](../../../docs/releasing.md). Git tags determine versions;
do not edit a static version field or set a version override. Ask for the desired
version if the request does not identify one; do not infer a release bump from
commit messages. Use `master`, and fully qualified refs when working with tags:
a branch named `v0.0.0` can coexist with a tag of the same name.

Use `make build`, `make check-dist`, and `make check` for validation. Ordinary
builds can have development versions, but release artifacts must match their tag.
`make release-notes VERSION=1.2.0` previews notes without modifying tracked files.

For an authorized local release preparation, run `make release VERSION=1.2.0`
on clean master. Candidate versions such as `1.2.0rc1` keep pending fragments;
final releases consume them into the changelog. Preparation creates only local
state and prints the explicit push command. Use
`uv run python -m scripts.release --dry-run 1.2.0` for a requested rehearsal.

Push only if the user requested pushing, using the exact atomic push command
reported by preparation. Tag pushes validate without publishing. Publish only
when requested, using `make publish TAG=v1.2.0`; candidates go to TestPyPI and
final releases go to PyPI. A successful Git push is not publication success.
The helper tracks its specific Actions dispatch and returns publication failures.

Do not recreate or move an existing tag after failure. Inspect the retained
checkout or workflow logs, explain partial completion, and follow the guide's
recovery procedure. Never retry uploads blindly after a timeout or partial upload.
Publisher configuration is an account setup step; inspect it when an
`invalid-publisher` error occurs. Report the exact tag, destination, and outcome.
