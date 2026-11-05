# Resolve paths with roots and anchors

[paths.py](../../examples/paths.py) needs core Confidantic and uses a temporary root.
It resolves paths without creating the application directories.

```console
uv run python examples/paths.py
```

## Declare dependencies in field order

Excerpt after importing BasePaths and ExtensiblePath:

```python
class Paths(BasePaths):
    """Application directories resolved relative to root and earlier fields."""

    data: ExtensiblePath = ExtensiblePath("data")
    """Data directory relative to root."""
    cache: ExtensiblePath = ExtensiblePath("@data/cache")
    """Cache directory relative to data."""
```

Root is canonicalized first. Data joins root; cache uses data as an earlier anchor.
An unknown or forward anchor fails validation. Declared fields must have concrete
Path-compatible annotations. Extra path values are also supported.

The script checks `paths.data("items.json")` and `paths("report.txt")` as callable
joining shortcuts. Absolute segments follow pathlib joining rules and can replace
earlier segments.

## Relocate explicitly

The following excerpt runs inside the temporary-directory block:

```python
moved = paths.copy(root=root / "next")
assert moved.data == paths.data
assert moved.cache == paths.cache
```

Stored values are already absolute. The next operation supplies fresh relative
definitions, `moved.copy(data="data", cache="@data/cache")`, so both paths follow
the new root. The original remains unchanged. On POSIX the stable output is
`next/data/cache`; separators follow the platform.

Unlike AbsolutePath, BasePaths expands home markers and supports root/anchor rules.
Existence constraints validate before canonicalization, so relative FilePath checks
use the current working directory.

Read [configuration models](../concepts/configuration-models.md),
[path internals](../api/paths.md), and [all guides](README.md).
