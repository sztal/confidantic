"""Build and validate the exact distributions intended for publication."""

import argparse
import os
import shutil
import subprocess
import tarfile
import zipfile
from collections.abc import Sequence
from email.message import Message
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.utils import parse_sdist_filename, parse_wheel_filename

from scripts._repository import clean, git, tag_version, verify_tag
from scripts.check_optional_dependencies import check_wheel


def build(project: Path) -> None:
    """Replace the distribution directory only after a successful fresh build."""
    if os.environ.get("UV_DYNAMIC_VERSIONING_BYPASS"):
        raise ValueError("Version overrides are not allowed for package builds")
    destination = project / "dist"
    if destination.is_symlink():
        raise ValueError("Distribution directory must not be a symlink")
    with TemporaryDirectory(prefix="confidantic-build-") as temporary:
        output = Path(temporary) / "dist"
        subprocess.run(
            ["uv", "build", "--no-sources", "--out-dir", str(output), str(project)],
            check=True,
        )
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(output, destination)


def metadata(path: Path) -> Message:
    """Read distribution metadata, requiring package code, typing, and license files."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            entries = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(entries) != 1 or not {
                "confidantic/__init__.py",
                "confidantic/py.typed",
            }.issubset(names):
                raise ValueError("Wheel is missing metadata, package code, or py.typed")
            if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
                raise ValueError("Wheel is missing its license")
            return BytesParser().parsebytes(archive.read(entries[0]))
    with tarfile.open(path) as archive:
        names = archive.getnames()
        root = path.name.removesuffix(".tar.gz")
        required = {
            f"{root}/{name}"
            for name in (
                "PKG-INFO",
                "pyproject.toml",
                "README.md",
                "LICENSE",
                "confidantic/__init__.py",
                "confidantic/py.typed",
            )
        }
        if not required.issubset(names):
            raise ValueError("Source distribution is missing required files")
        stream = archive.extractfile(f"{root}/PKG-INFO")
        if stream is None:
            raise ValueError("Source distribution metadata is not a regular file")
        return BytesParser().parsebytes(stream.read())


def inspect_distributions(directory: Path, tag: str | None = None) -> tuple[Path, Path]:
    """Require one matching wheel/sdist pair and optional exact tag version.

    Parameters
    ----------
    directory
        Directory containing only the wheel and sdist (plus optional .gitignore).
    tag
        Canonical release tag, or None to permit Git-derived development versions.

    Returns
    -------
    tuple of Path
        Validated wheel and source archive paths.
    """
    files = {path for path in directory.iterdir() if path.name != ".gitignore"}
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1 or files != {*wheels, *sources}:
        raise ValueError(
            "Expected exactly one wheel and one sdist; rebuild stale artifacts"
        )
    wheel, sdist = wheels[0], sources[0]
    wheel_name, wheel_version, _, _ = parse_wheel_filename(wheel.name)
    source_name, source_version = parse_sdist_filename(sdist.name)
    if (
        wheel_name != "confidantic"
        or source_name != wheel_name
        or source_version != wheel_version
    ):
        raise ValueError("Distribution names and versions do not match")
    if tag is not None and wheel_version != tag_version(tag):
        raise ValueError("Distribution version does not match the release tag")
    wheel_metadata, source_metadata = metadata(wheel), metadata(sdist)
    for info in (wheel_metadata, source_metadata):
        if info["Name"] != "confidantic" or info["Version"] != str(wheel_version):
            raise ValueError("Distribution metadata does not match its filename")
        if info["Requires-Python"] != ">=3.11" or info["License-Expression"] != "MIT":
            raise ValueError("Distribution Python or license metadata is incorrect")
    if sorted(wheel_metadata.get_all("Requires-Dist", [])) != sorted(
        source_metadata.get_all("Requires-Dist", [])
    ):
        raise ValueError("Wheel and sdist dependencies differ")
    return wheel, sdist


def check_distributions(project: Path, tag: str | None = None) -> None:
    """Check metadata, rebuild the sdist outside Git, and smoke-test exact wheels."""
    if os.environ.get("UV_DYNAMIC_VERSIONING_BYPASS"):
        raise ValueError("Version overrides are not allowed for distribution checks")
    if tag:
        clean(project)
        commit = verify_tag(project, tag, "HEAD")
        if commit != git(project, "rev-parse", "HEAD"):
            raise ValueError("Release checks must run at the tagged commit")
    wheel, sdist = inspect_distributions(project / "dist", tag)
    subprocess.run(["twine", "check", "--strict", str(wheel), str(sdist)], check=True)
    check_wheel(wheel)
    with TemporaryDirectory(prefix="confidantic-sdist-") as temporary:
        output = Path(temporary)
        subprocess.run(
            [
                "uv",
                "build",
                "--no-sources",
                "--wheel",
                "--out-dir",
                str(output),
                str(sdist),
            ],
            cwd=output,
            check=True,
        )
        (rebuilt,) = output.glob("*.whl")
        original = metadata(wheel)
        if metadata(rebuilt)["Version"] != original["Version"]:
            raise ValueError("Source rebuild changed the package version")
        check_wheel(rebuilt, ("core",))


def main(argv: Sequence[str] | None = None) -> None:
    """Build or check distributions in the current project, optionally for a tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--tag")
    args = parser.parse_args(argv)
    if args.command == "build":
        build(Path.cwd())
    else:
        check_distributions(Path.cwd(), args.tag)


if __name__ == "__main__":
    main()
