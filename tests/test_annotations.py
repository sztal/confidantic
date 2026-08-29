"""Tests for public annotation helpers."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, DirectoryPath, FilePath, ValidationError
from pytest import MonkeyPatch, raises

from confidantic.annotations import (
    AbsolutePath,
    Call,
    Import,
    Make,
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


def test_call_invokes_callables_import_strings_and_call_mappings() -> None:
    """Call annotations evaluate all supported directive forms before validation."""

    class Settings(BaseModel):
        value: Call[dict[str, int]]
        items: Call[tuple[int, int]]

    settings = Settings.model_validate(
        {
            "value": {"@call": "builtins:dict", "answer": 42},
            "items": {"@call": "builtins:tuple", "@args": [[1, 2]]},
        }
    )

    assert Settings(value=dict, items=lambda: (1, 2)).value == {}
    assert Settings(value="builtins:dict", items=lambda: (1, 2)).value == {}
    assert settings.value == {"answer": 42}
    assert settings.items == (1, 2)


def test_call_rejects_mappings_without_a_call_target() -> None:
    """Call mappings must explicitly identify their callable target."""

    class Settings(BaseModel):
        value: Call[dict[str, int]]

    with raises(ValidationError, match="Call mappings require an '@call' key"):
        Settings.model_validate({"value": {"answer": 42}})


def test_make_recursively_evaluates_nested_call_mappings() -> None:
    """Make evaluates nested call mappings while preserving ordinary mappings."""

    class Settings(BaseModel):
        value: Make[dict[str, list[dict[str, int]]]]

    settings = Settings.model_validate(
        {
            "value": {
                "items": [
                    {"@call": "builtins:dict", "answer": 42},
                ]
            }
        }
    )

    assert settings.value == {"items": [{"answer": 42}]}
