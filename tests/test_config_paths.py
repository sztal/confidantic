"""Tests for path-oriented configuration models."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import EnvSettingsSource

from confidantic import ConfigModelDict as ConfigModelDict
from confidantic.paths import BasePaths, ExtensiblePath


def _build_paths(
    settings_cls: type[BasePaths] = BasePaths,
    **kwargs: Any,
) -> Any:
    return settings_cls(**kwargs)


def test_dynamic_path_call_joins_path_segments() -> None:
    """Calling a dynamic path delegates to ``joinpath`` and stays dynamic."""
    path = ExtensiblePath("data")

    joined = path("raw", Path("items.json"))

    assert isinstance(path, Path)
    assert type(joined) is ExtensiblePath
    assert joined == path.joinpath("raw", "items.json")
    assert joined("archive") == path.joinpath("raw", "items.json", "archive")


def test_base_paths_call_joins_segments_to_root(tmp_path: Path) -> None:
    """Calling a paths model delegates to its root path."""
    paths = _build_paths(root=tmp_path)

    joined = paths("data", Path("items.json"))

    assert type(joined) is ExtensiblePath
    assert joined == paths.root.joinpath("data", "items.json")

    with pytest.raises(TypeError):
        paths(segment="data")


def test_dynamic_path_has_no_dynamic_segment_attributes() -> None:
    """Unknown attributes do not append path segments."""
    path = ExtensiblePath("data")

    assert not hasattr(path, "raw")


def test_relative_root_and_declared_defaults_are_canonicalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative roots use cwd and declared defaults resolve below root."""

    class ProjectPaths(BasePaths):
        data: ExtensiblePath = ExtensiblePath("data/../raw")
        generated: ExtensiblePath = ExtensiblePath("generated")

    monkeypatch.chdir(tmp_path)
    paths = _build_paths(ProjectPaths, root="project/./source/..")

    assert paths.root == (tmp_path / "project").resolve(strict=False)
    assert paths.data == (tmp_path / "project/raw").resolve(strict=False)
    assert paths.generated == (tmp_path / "project/generated").resolve(strict=False)
    assert type(paths.root) is ExtensiblePath
    assert type(paths.data) is ExtensiblePath


def test_home_expansion_precedes_root_joining(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Home-based paths become absolute before secondary paths use root."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    paths = _build_paths(root="~/project/..", cache="~/cache/../data")

    assert paths.root == home.resolve(strict=False)
    assert paths.cache == (home / "data").resolve(strict=False)


def test_absolute_secondary_path_bypasses_root_but_is_canonicalized(
    tmp_path: Path,
) -> None:
    """Absolute definitions skip joining and still collapse path components."""
    paths = _build_paths(
        root=tmp_path / "project",
        cache=tmp_path / "outside" / ".." / "cache",
    )

    assert paths.cache == (tmp_path / "cache").resolve(strict=False)


def test_existing_symlink_components_are_canonicalized(tmp_path: Path) -> None:
    """Non-strict resolution follows existing symlinks without requiring leaves."""
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    paths = _build_paths(root=link / "project", data="missing")

    assert paths.root == target / "project"
    assert paths.data == target / "project/missing"


def test_extra_paths_are_validated_and_available_as_attributes(
    tmp_path: Path,
) -> None:
    """Allowed extras remain path-only and resolve against root."""
    paths = _build_paths(root=tmp_path, data="data", cache=Path("cache"))

    assert type(paths.data) is ExtensiblePath
    assert type(paths.cache) is ExtensiblePath
    assert paths.data == tmp_path / "data"
    assert paths.cache == tmp_path / "cache"

    with pytest.raises(ValidationError):
        _build_paths(root=tmp_path, retries=3)


def test_non_path_declared_fields_are_rejected() -> None:
    """Subclasses cannot weaken the path-only field contract."""
    with pytest.raises(TypeError, match="retries"):

        class InvalidPaths(BasePaths):
            retries: int = 3


def test_path_annotated_fields_are_canonicalized_to_dynamic_paths(
    tmp_path: Path,
) -> None:
    """Path annotations accept path inputs and retain the dynamic path API."""

    class ProjectPaths(BasePaths):
        data: Path = Path("data")

    paths = _build_paths(ProjectPaths, root=tmp_path)

    assert paths.data == tmp_path / "data"
    assert type(paths.data) is ExtensiblePath
    assert paths.data("raw") == tmp_path / "data/raw"


def test_environment_paths_are_resolved_and_retain_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment strings use normal settings resolution before canonicalization."""

    class EnvironmentPaths(BasePaths):
        model_config = ConfigModelDict(env_prefix="APP_")

        data: ExtensiblePath

    monkeypatch.setenv("APP_ROOT", str(tmp_path / "project"))
    monkeypatch.setenv("APP_DATA", "data/../raw")

    paths = _build_paths(EnvironmentPaths)

    assert paths.root == tmp_path / "project"
    assert paths.data == tmp_path / "project/raw"
    assert paths.model_field_sources == {
        "root": (EnvSettingsSource, EnvironmentPaths),
        "data": (EnvSettingsSource, EnvironmentPaths),
    }


def test_paths_are_frozen_and_trusted_copies_accept_dynamic_paths(
    tmp_path: Path,
) -> None:
    """Models stay frozen while trusted copies can use canonical dynamic values."""
    paths = _build_paths(root=tmp_path, data="data")

    with pytest.raises(ValidationError):
        paths.root = ExtensiblePath("other")

    replacement = ExtensiblePath(tmp_path / "replacement").resolve(strict=False)
    copied = paths.model_copy(update={"data": replacement})

    assert copied.data == replacement
    assert type(copied.data) is ExtensiblePath


def test_serialization_uses_canonical_paths(tmp_path: Path) -> None:
    """Python dumps retain paths while JSON dumps and round trips use strings."""
    paths = _build_paths(root=tmp_path / "project/..", data="data/../raw")

    python_dump = paths.model_dump()
    json_dump = paths.model_dump(mode="json")
    restored = BasePaths.model_validate_json(paths.model_dump_json())

    assert type(python_dump["root"]) is ExtensiblePath
    assert type(python_dump["data"]) is ExtensiblePath
    assert json_dump == {"root": str(tmp_path), "data": str(tmp_path / "raw")}
    assert restored == paths


def test_at_prefixed_paths_resolve_against_previously_defined_fields(
    tmp_path: Path,
) -> None:
    """At-prefixed paths resolve from a previously canonicalized path field."""

    class ProjectPaths(BasePaths):
        config: Path = Path("@root/config")
        data: Path = Path("@config/data")
        cache: Path = Path("@data/cache")

    paths = _build_paths(ProjectPaths, root=tmp_path)

    assert paths.config == tmp_path / "config"
    assert paths.data == tmp_path / "config/data"
    assert paths.cache == tmp_path / "config/data/cache"


def test_at_prefixed_paths_reject_unknown_and_forward_anchors(tmp_path: Path) -> None:
    """At-prefixed paths cannot reference fields defined later."""

    class ProjectPaths(BasePaths):
        data: Path = Path("@config/data")
        config: Path = Path("config")

    with pytest.raises(
        ValidationError, match="Unknown or forward path anchor: @config"
    ):
        _build_paths(ProjectPaths, root=tmp_path)


def test_at_prefixed_extra_paths_resolve_against_previous_extras(
    tmp_path: Path,
) -> None:
    """Extra paths can anchor to extras provided earlier in the input."""
    paths = _build_paths(
        root=tmp_path,
        config="config",
        data="@config/data",
    )

    assert paths.config == tmp_path / "config"
    assert paths.data == tmp_path / "config/data"
