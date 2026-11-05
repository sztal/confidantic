# %% Define paths in dependency order -----------------------------------------------

"""Resolve relative paths and anchors without creating application directories."""

from pathlib import Path
from tempfile import TemporaryDirectory

from confidantic.paths import BasePaths, ExtensiblePath


class Paths(BasePaths):
    """Application directories resolved relative to root and earlier fields."""

    data: ExtensiblePath = ExtensiblePath("data")
    """Data directory relative to root."""
    cache: ExtensiblePath = ExtensiblePath("@data/cache")
    """Cache directory relative to data."""


with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    paths = Paths(root=root)
    assert paths.data == root / "data"
    assert paths.cache == root / "data" / "cache"
    assert paths.data("items.json") == root / "data" / "items.json"
    assert paths("report.txt") == root / "report.txt"
    assert not paths.data.exists()

    # %% Moving root preserves already resolved absolute paths ----------------------

    moved = paths.copy(root=root / "next")
    assert moved.data == paths.data
    assert moved.cache == paths.cache

    # Supply relative definitions again for paths that should follow the new root.
    relocated = moved.copy(data="data", cache="@data/cache")
    assert relocated.data == moved.root / "data"
    assert relocated.cache == moved.root / "data" / "cache"
    assert paths.root == root
    print(relocated.cache.relative_to(root))
