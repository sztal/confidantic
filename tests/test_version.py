"""The test for the version attribute."""

import importlib.metadata

from confidantic import __version__


def test_version() -> None:
    """Test that the version attribute matches the package version."""
    version = importlib.metadata.version("confidantic")
    assert __version__ == version
