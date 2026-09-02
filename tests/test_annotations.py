"""Tests for public annotation helpers."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel, DirectoryPath, FilePath, TypeAdapter, ValidationError
from pytest import MonkeyPatch, raises

from confidantic import BaseConfig
from confidantic.annotations import (
    AbsolutePath,
    Call,
    CommaDelimited,
    Delimited,
    Import,
    Make,
    Map,
    SemiColonDelimited,
    WhitespaceDelimited,
    get_proper_args,
)
from confidantic.utils import make


def test_absolute_path_annotation_accepts_path_values() -> None:
    """The default annotation is assignable from ordinary paths."""
    path: AbsolutePath = Path(".")

    assert path == Path(".")


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


@pytest.mark.parametrize(
    ("annotation", "value"),
    [
        (Delimited("|"), "1 | 2|3"),
        (CommaDelimited, "1, 2,3"),
        (SemiColonDelimited, "1; 2;3"),
        (WhitespaceDelimited, "1  2\t3"),
    ],
)
def test_delimited_annotations_parse_strings_and_sequences(
    annotation: object,
    value: str,
) -> None:
    """Delimited annotations split strings but accept normal sequences."""
    adapter = TypeAdapter(annotation[list[int]])  # type: ignore[index]

    assert adapter.validate_python(value) == [1, 2, 3]
    assert adapter.validate_python([4, 5]) == [4, 5]


def test_delimited_annotations_preserve_item_validation_errors() -> None:
    """Split items still undergo validation against the annotated sequence type."""
    adapter = TypeAdapter(CommaDelimited[list[int]])

    with raises(ValidationError):
        adapter.validate_python("one, two")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--values", "[1, 2]"], [1, 2]),
        (["--values", "1", "--values", "2"], [1, 2]),
        (["--values", "1,2"], [1, 2]),
    ],
)
def test_delimited_annotations_support_standard_cli_list_formats(
    arguments: list[str],
    expected: list[int],
) -> None:
    """Delimited annotations retain Pydantic Settings CLI list formats."""

    class Settings(BaseConfig, cli_parse_args=True):
        values: CommaDelimited[list[int]]

    assert Settings(_cli_parse_args=arguments).values == expected


def test_delimited_annotations_parse_environment_and_dotenv_values(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Delimited annotations parse comma-separated environment and dotenv values."""

    class Settings(BaseConfig, env_prefix="DELIMITED_"):
        values: CommaDelimited[list[int]]

    monkeypatch.setenv("DELIMITED_VALUES", "1,2")
    assert Settings().values == [1, 2]

    monkeypatch.delenv("DELIMITED_VALUES")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DELIMITED_VALUES=1,2\n", encoding="utf-8")
    assert Settings(_env_file=dotenv_path).values == [1, 2]


def test_map_annotations_parse_strings_and_mappings() -> None:
    """Map annotations parse flexible key-value strings and preserve mappings."""
    adapter = TypeAdapter(Map[dict[str, int]])

    assert adapter.validate_python("first=1, second=2") == {"first": 1, "second": 2}
    assert adapter.validate_python("first=1, second=2, third=3,") == {
        "first": 1,
        "second": 2,
        "third": 3,
    }
    assert adapter.validate_python("first=1 second=2") == {"first": 1, "second": 2}
    assert adapter.validate_python('{"first": 1, "second": 2}') == {
        "first": 1,
        "second": 2,
    }
    assert adapter.validate_python({"first": 1, "second": 2}) == {
        "first": 1,
        "second": 2,
    }


def test_map_annotations_preserve_mapping_validation_errors() -> None:
    """Map values retain validation errors for invalid keys and values."""
    adapter = TypeAdapter(Map[dict[str, int]])

    with raises(ValidationError):
        adapter.validate_python("first=one")
    with raises(ValidationError):
        adapter.validate_python("first")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--values", '{"first": 1, "second": 2}'], {"first": 1, "second": 2}),
        (["--values", "first=1,second=2"], {"first": 1, "second": 2}),
    ],
)
def test_map_annotations_support_standard_cli_mapping_formats(
    arguments: list[str],
    expected: dict[str, int],
) -> None:
    """Map annotations retain Pydantic Settings CLI mapping formats."""

    class Settings(BaseConfig, cli_parse_args=True):
        values: Map[dict[str, int]]

    assert Settings(_cli_parse_args=arguments).values == expected


def test_map_annotations_parse_environment_and_dotenv_values(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Map annotations parse key-value environment and dotenv values."""

    class Settings(BaseConfig, env_prefix="DICT_LIKE_"):
        values: Map[dict[str, int]]

    monkeypatch.setenv("DICT_LIKE_VALUES", "first=1,second=2")
    assert Settings().values == {"first": 1, "second": 2}

    monkeypatch.delenv("DICT_LIKE_VALUES")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DICT_LIKE_VALUES=first=1,second=2\n", encoding="utf-8")
    assert Settings(_env_file=dotenv_path).values == {"first": 1, "second": 2}


def test_import_resolves_import_strings_and_serializes_objects() -> None:
    """Import annotations resolve strings and dump stable import paths."""

    class Settings(BaseModel):
        callable: Import[Callable]

    settings = Settings.model_validate({"callable": "builtins:len"})

    assert settings.callable is len
    assert settings.model_dump() == {"callable": "builtins:len"}
    assert Settings(callable=len).model_dump_json() == '{"callable":"builtins:len"}'
    assert Settings.model_validate_json(settings.model_dump_json()).callable is len


def test_import_accepts_class_defaults() -> None:
    """Import annotations retain class objects as typed configuration defaults."""

    class Settings(BaseConfig):
        collection: Import[type[Counter]] = Counter

    settings = Settings()

    assert settings.collection is Counter
    assert settings.model_dump(mode="json") == {"collection": "collections:Counter"}


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


def test_call_and_make_pass_ordinary_values_to_pydantic_validation() -> None:
    """Values without directives are validated as the annotations' output types."""

    class Settings(BaseModel):
        call_value: Call[int]
        call_mapping: Call[dict[str, int]]
        make_value: Make[int]
        make_mapping: Make[dict[str, int]]

    settings = Settings.model_validate(
        {
            "call_value": 3,
            "call_mapping": {"answer": 42},
            "make_value": 4,
            "make_mapping": {"answer": 43},
        }
    )

    assert settings.call_value == 3
    assert settings.call_mapping == {"answer": 42}
    assert settings.make_value == 4
    assert settings.make_mapping == {"answer": 43}


@pytest.mark.parametrize(
    "annotation",
    [Call[int], Make[int]],
    ids=["call", "make"],
)
def test_directive_annotations_reject_non_iterable_arguments(
    annotation: object,
) -> None:
    """Directive arguments must be iterable for Python's positional calling syntax."""
    adapter = TypeAdapter(annotation)

    with raises(ValidationError, match="'@args' must be an iterable"):
        adapter.validate_python({"@call": "builtins:int", "@args": 3})


@pytest.mark.parametrize(
    ("annotation", "value", "expected"),
    [
        (
            Make[list[dict[str, int]]],
            [{"@call": "builtins:dict", "answer": 42}],
            [{"answer": 42}],
        ),
        (
            Make[tuple[dict[str, int], ...]],
            ({"@call": "builtins:dict", "answer": 42},),
            ({"answer": 42},),
        ),
    ],
)
def test_make_resolves_directives_in_top_level_sequences(
    annotation: object,
    value: object,
    expected: object,
) -> None:
    """Make recursively resolves directives in list and tuple field values."""
    assert TypeAdapter(annotation).validate_python(value) == expected


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


def test_make_can_evaluate_values_without_a_pydantic_handler() -> None:
    """The standalone helper returns the value a Make field would receive."""
    value = make(
        {
            "items": [
                {"@call": "builtins:dict", "answer": 42},
            ]
        }
    )

    assert value == {"items": [{"answer": 42}]}


def test_make_preserves_nested_constructed_values() -> None:
    """Make passes values built by nested directives to normal validation."""

    class Child(BaseModel):
        value: int

    class Parent(BaseModel):
        child: Make[Child]

    class Settings(BaseModel):
        parent: Make[Parent]

    settings = Settings.model_validate(
        {
            "parent": {
                "@call": Parent,
                "child": {"@call": Child, "value": 42},
            }
        }
    )

    assert settings.parent.child == Child(value=42)
