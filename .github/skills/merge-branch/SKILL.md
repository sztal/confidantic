---
name: merge-branch
description: Entry point for preparing or performing Confidantic's existing branch integration into master.
argument-hint: Source branch and requested preparation or merge stage
---

# Merge Branch

Follow [merge-to-master](../merge-to-master/SKILL.md) and
[the release guide](../../../docs/releasing.md). This skill delegates to that
workflow; it does not define a second merge procedure.

Confidantic integrates into `master` using the isolated, ancestry-preserving
Make helpers. Preserve reference revalidation, duplicate-merge detection, and
consolidated Towncrier notes. Do not substitute a squash merge. For a requested
target other than `master`, explain that these helpers support only `master` and
resolve the intended workflow before applying a merge.

Preparation uses `make merge-check`; an authorized merge uses `make merge`.
A review request does not authorize merging, and neither stage authorizes pushes,
tags, or publication. Preserve user work and report conflicts or failed checks.
