"""Distribution contents, version coherence, and checking the supplied artifacts."""

import io
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
from packaging.utils import parse_wheel_filename
from packaging.version import Version

from scripts import distributions
from scripts._repository import git


def artifacts(
    directory: Path,
    version: str = "1.2.3",
    *,
    typed: bool = True,
    requires_python: str = ">=3.13",
) -> tuple[Path, Path]:
    """Write small but structurally valid distributions for metadata checks."""
    directory.mkdir(exist_ok=True)
    info = f"Metadata-Version: 2.4\nName: confidantic\nVersion: {version}\nRequires-Python: {requires_python}\nLicense-Expression: MIT\nRequires-Dist: pydantic>=2.14\n\nDescription\n"
    wheel = directory / f"confidantic-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"confidantic-{version}.dist-info/METADATA", info)
        archive.writestr(f"confidantic-{version}.dist-info/licenses/LICENSE", "MIT")
        archive.writestr("confidantic/__init__.py", "")
        if typed:
            archive.writestr("confidantic/py.typed", "")
    sdist = directory / f"confidantic-{version}.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        for name in (
            "PKG-INFO",
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "src/confidantic/__init__.py",
            "src/confidantic/py.typed",
        ):
            content = info.encode() if name == "PKG-INFO" else b"content"
            entry = tarfile.TarInfo(f"confidantic-{version}/{name}")
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    return wheel, sdist


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3rc1", "1.2.3a2", "1.2.3b1"])
def test_matching_release_metadata(tmp_path: Path, version: str) -> None:
    pair = artifacts(tmp_path, version)
    assert distributions.inspect_distributions(tmp_path, f"v{version}") == pair


def test_development_build_is_not_release(tmp_path: Path) -> None:
    artifacts(tmp_path, "1.2.3.post1.dev0+abc123")
    distributions.inspect_distributions(tmp_path)
    with pytest.raises(ValueError, match="does not match"):
        distributions.inspect_distributions(tmp_path, "v1.2.3")


def test_distribution_rejects_old_python_requirement(tmp_path: Path) -> None:
    artifacts(tmp_path, requires_python=">=3.11")
    with pytest.raises(ValueError, match="Python or license metadata"):
        distributions.inspect_distributions(tmp_path)


@pytest.mark.parametrize(
    "problem", ["stale", "mixed", "missing", "extra", "typed", "metadata"]
)
def test_bad_artifact_sets(tmp_path: Path, problem: str) -> None:
    wheel, sdist = artifacts(tmp_path, typed=problem != "typed")
    if problem == "stale":
        artifacts(tmp_path, "1.2.4")
    elif problem == "mixed":
        wheel.rename(tmp_path / "confidantic-1.2.4-py3-none-any.whl")
    elif problem == "missing":
        sdist.unlink()
    elif problem == "extra":
        (tmp_path / "unexpected.txt").write_text("stale output")
    elif problem == "metadata":
        wheel.rename(tmp_path / "confidantic-1.2.4-py3-none-any.whl")
        sdist.rename(tmp_path / "confidantic-1.2.4.tar.gz")
    with pytest.raises(ValueError):
        distributions.inspect_distributions(tmp_path)


def test_supplied_wheel_and_sdist_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel, sdist = artifacts(tmp_path / "dist")
    checked: list[tuple[Path, tuple[str, ...] | None]] = []
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "uv":
            assert command[-1] == str(sdist)
            output = Path(command[command.index("--out-dir") + 1])
            assert kwargs["cwd"] == output
            assert not (output / ".git").exists()
            rebuilt, source = artifacts(output)
            source.unlink()
            assert rebuilt.name == wheel.name
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(distributions.subprocess, "run", run)
    monkeypatch.setattr(
        distributions,
        "check_wheel",
        lambda path, profiles=None: checked.append((path, profiles)),
    )
    distributions.check_distributions(tmp_path)
    assert checked[0] == (wheel, None)
    assert checked[1][1] == ("core",)
    assert commands[0] == ["twine", "check", "--strict", str(wheel), str(sdist)]


def test_failed_build_preserves_previous_dist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel, sdist = artifacts(tmp_path / "dist")

    def fail(*args: Any, **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(1, "uv build")

    monkeypatch.setattr(distributions.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        distributions.build(tmp_path)
    assert wheel.exists() and sdist.exists()


@pytest.mark.parametrize(
    "name",
    [
        "SETUPTOOLS_SCM_PRETEND_VERSION",
        "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CONFIDANTIC",
    ],
)
def test_version_override_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "1.2.3")
    with pytest.raises(ValueError, match="overrides"):
        distributions.build(tmp_path)
    with pytest.raises(ValueError, match="overrides"):
        distributions.check_distributions(tmp_path)


def test_vcs_versions_ignore_lightweight_tags(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build from real Git tags using the repository's Hatch configuration."""
    for name in tuple(os.environ):
        if name == "SETUPTOOLS_SCM_PRETEND_VERSION" or name.startswith(
            "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_"
        ):
            monkeypatch.delenv(name)

    root = Path(__file__).resolve().parents[2]
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        (repository / name).write_bytes((root / name).read_bytes())
    package = repository / "src/confidantic"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "py.typed").write_text("")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Configure package")

    def build_version(name: str) -> Version:
        output = tmp_path / name
        subprocess.run(
            [
                "uv",
                "build",
                "--no-sources",
                "--wheel",
                "--out-dir",
                str(output),
                str(repository),
            ],
            cwd=tmp_path,
            check=True,
        )
        (wheel,) = output.glob("*.whl")
        return parse_wheel_filename(wheel.name)[1]

    git(repository, "tag", "-a", "v1.2.3", "-m", "Release 1.2.3")
    assert str(build_version("annotated")) == "1.2.3"
    git(repository, "tag", "v9.0.0")
    assert str(build_version("lightweight")) == "1.2.3"

    git(repository, "commit", "--allow-empty", "-qm", "Next change")
    clean_version = build_version("development")
    assert clean_version.is_devrelease
    assert clean_version.base_version != "9.0.0"
    (repository / "tracked").write_text("dirty\n")
    assert build_version("dirty") != clean_version

    (repository / "tracked").write_text("baseline\n")
    git(repository, "tag", "-a", "v1.2.4rc1", "-m", "Release 1.2.4rc1")
    assert str(build_version("prerelease")) == "1.2.4rc1"
