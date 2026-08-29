"""Tests for public annotation helpers."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, DirectoryPath, FilePath, ValidationError
from pytest import MonkeyPatch, raises

from confidantic.annotations import (
    AbsolutePath,
    Import,
    get_proper_args,
)


def test_get_proper_args_extracts_types_from_nested_annotations() -> None:
    """Concrete types are extracted from unions and annotated types."""
    annotation = list[Annotated[int | str, "metadata"]]

    assert list(get_proper_args(annotation)) == [int, str]


def test_absolute_path_resolves_paths_from_the_current_directory(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The default annotation resolves a path after normal Path validation."""

    class Settings(BaseModel):
        path: AbsolutePath

    monkeypatch.chdir(tmp_path)

    settings = Settings.model_validate({"path": "missing/../config.toml"})

    assert settings.path == tmp_path / "config.toml"


def test_absolute_path_retains_specialized_path_validation(tmp_path: Path) -> None:
    """Specialized annotations validate their path kind before resolution."""

    class Settings(BaseModel):
        file: AbsolutePath[FilePath]
        directory: AbsolutePath[DirectoryPath]

    file_path = tmp_path / "config.toml"
    file_path.touch()
    directory_path = tmp_path / "config"
    directory_path.mkdir()

    settings = Settings.model_validate({"file": file_path, "directory": directory_path})

    assert settings.file == file_path.resolve()
    assert settings.directory == directory_path.resolve()
    with raises(ValidationError):
        Settings.model_validate({"file": directory_path, "directory": file_path})


def test_import_resolves_import_strings_and_serializes_objects() -> None:
    """Import annotations resolve strings and dump stable import paths."""

    class Settings(BaseModel):
        callable: Import[Callable]

    settings = Settings.model_validate({"callable": "builtins:len"})

    assert settings.callable is len
    assert settings.model_dump() == {"callable": "builtins:len"}
    assert Settings(callable=len).model_dump_json() == '{"callable":"builtins:len"}'
    assert Settings.model_validate_json(settings.model_dump_json()).callable is len
