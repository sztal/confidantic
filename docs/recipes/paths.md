# Organize application directories

[BasePaths][confidantic.paths.BasePaths] resolves related directories from a common
root. [ExtensiblePath][confidantic.paths.ExtensiblePath] adds convenient path joining.
This recipe needs only core Confidantic and creates no application directories.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from confidantic.paths import BasePaths, ExtensiblePath


class Paths(BasePaths):
    data: ExtensiblePath = ExtensiblePath("data")
    cache: ExtensiblePath = ExtensiblePath("@data/cache")


with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    paths = Paths(root=root)
    print(paths.cache.relative_to(root).as_posix())
    print(paths.data("items.json").relative_to(root).as_posix())
    print(paths("report.txt").relative_to(root).as_posix())
    print(paths.data.exists())
```

```text
data/cache
data/items.json
report.txt
False
```

`data` joins the root. The `@data` anchor makes `cache` relative to the earlier
`data` field. Declare dependencies in field order: unknown and forward anchors
fail validation. Declared path fields need concrete Path-compatible annotations;
extra path values are also supported.

Resolution and directory creation are separate. Create a required directory
explicitly with `paths.data.mkdir(parents=True, exist_ok=True)` when your application
is ready to use it. Absolute joined segments follow pathlib's rules and may
replace earlier segments.

## Relocate paths deliberately

Within the temporary-directory block above, these operations have different effects:

```python
moved = paths.copy(root=root / "next")
relocated = moved.copy(data="data", cache="@data/cache")
print(moved.cache == paths.cache)
print(relocated.cache.relative_to(root).as_posix())
```

They print `True` and `next/data/cache`. Stored paths are already absolute, so a
new root alone does not rebase them. Supplying relative definitions again makes
those paths follow the new root.

`BasePaths` expands home markers and applies roots and anchors.
[AbsolutePath](../guide/input-parsing.md#resolve-a-filesystem-path) only resolves a
path against the working directory. Existence constraints run before canonicalization,
so a relative `FilePath` check uses the current working directory.

For implementation details, see the
[wiki paths reference](https://github.com/sztal/confidantic/blob/master/wiki/api/paths.md).
