# Develop Confidantic

Use this section when contributing code, documentation, or a release. Start with
[AGENTS.md](../../AGENTS.md), [STYLE.md](../../STYLE.md), and
[test placement](../../tests/README.md); these remain the repository's working
rules. Package users can start with the [handbook](../README.md).

## Set up the checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the repository root:

```console
uv python install
uv sync --group dev --group docs --extra all
```

`uv python install` reads [.python-version](../../.python-version), currently
3.15. The package supports Python 3.13 and later. Dependency groups, supported
versions, and check settings live in [pyproject.toml](../../pyproject.toml).

## Find the owning component

| Location               | Responsibility                                                       |
| ---------------------- | -------------------------------------------------------------------- |
| `confidantic/`         | Public modules; configuration internals under `_config/`             |
| `tests/`               | Mirrored unit tests, subprocess integration checks, and script tests |
| `examples/`            | Runnable guides linked from the wiki                                 |
| `docs/`                | Published documentation built with Zensical                          |
| `wiki/`                | Repository handbook, architecture, and implementation reference      |
| `scripts/`, `Makefile` | Shared checks, merge preparation, builds, and releases               |
| `.github/skills/`      | Task-specific agent workflows                                        |

The [package map](../architecture/package-map.md) and
[API index](../api/README.md) connect implementation modules to behavioral tests.

## Choose a workflow

- [Contributing](contributing.md): branches, style, tests, and documentation checks.
- [Agent skills](agent-skills.md): choose a workflow and understand its scope.
- [Merging and releasing](releasing.md): integrate changes, consolidate notes,
  prepare a version, and publish explicitly.

Keep unresolved source defects in [BUGS.md](../../BUGS.md), never in wiki task
lists. Keep durable explanations here and runnable application guides in
[examples](../../examples/).
