"""Distribution contents, version coherence, and checking the supplied artifacts."""

import io
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts import distributions


def artifacts(
    directory: Path, version: str = "1.2.3", *, typed: bool = True
) -> tuple[Path, Path]:
    """Write small but structurally valid distributions for metadata checks."""
    directory.mkdir(exist_ok=True)
    info = f"Metadata-Version: 2.4\nName: confidantic\nVersion: {version}\nRequires-Python: >=3.11\nLicense-Expression: MIT\nRequires-Dist: pydantic>=2.14\n\nDescription\n"
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
            "confidantic/__init__.py",
            "confidantic/py.typed",
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


def test_version_override_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UV_DYNAMIC_VERSIONING_BYPASS", "1.2.3")
    with pytest.raises(ValueError, match="overrides"):
        distributions.build(tmp_path)
    with pytest.raises(ValueError, match="overrides"):
        distributions.check_distributions(tmp_path)
