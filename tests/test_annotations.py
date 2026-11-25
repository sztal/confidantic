"""Tests for public annotation helpers."""

from collections import Counter
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import pytest
from pydantic import (
    BaseModel,
    DirectoryPath,
    Field,
    FilePath,
    TypeAdapter,
    ValidationError,
)
from pydantic_settings import ForceDecode, NoDecode
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
    TabDelimited,
    WhitespaceDelimited,
    get_proper_args,
)


def test_absolute_path_annotation_accepts_path_values() -> None:
    """The unparameterized annotation validates ordinary Path inputs."""
    path: AbsolutePath = TypeAdapter(AbsolutePath).validate_python(Path("."))

    assert path == Path.cwd().resolve()


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
        (TabDelimited, "1\t2\t3"),
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
    ("annotation", "value", "expected"),
    [
        (CommaDelimited[list[str]], '["a,b", "c"]', ["a,b", "c"]),
        (CommaDelimited[list[str]], "a,,c", ["a", "", "c"]),
        (WhitespaceDelimited[list[str]], "a   c", ["a", "c"]),
        (Map[dict[str, str]], "a=first,a=last=b", {"a": "last=b"}),
    ],
)
def test_flexible_inputs_preserve_separator_semantics(
    annotation: Any, value: str, expected: Any
) -> None:
    """JSON quoting, empty items, duplicate keys, and embedded equals signs are stable."""
    assert TypeAdapter(annotation).validate_python(value) == expected


@pytest.mark.parametrize("value", [42, "invalid", '["invalid"]'])
def test_delimited_fallback_preserves_the_original_error(value: Any) -> None:
    """Unsuccessful parsing retains normal validation's error type and input."""
    with raises(ValidationError) as error:
        TypeAdapter(CommaDelimited[list[int]]).validate_python(value)
    assert error.value.errors()[0]["type"] == "list_type"
    assert error.value.errors()[0]["input"] == value


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
    with raises(ValidationError):
        adapter.validate_python(1)


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


class _UnionColor(Enum):
    RED = "red"
    BLUE = "blue"


type _FloatListAlias = CommaDelimited[list[float]]


@pytest.mark.parametrize(
    ("annotation", "default", "arguments", "expected"),
    [
        (float | CommaDelimited[tuple[float, float]], 0.0, ["--value=0.1"], 0.1),
        (
            float | CommaDelimited[tuple[float, float]],
            0.0,
            ["--value=0.1,0.2"],
            (0.1, 0.2),
        ),
        (
            float | CommaDelimited[tuple[float, float]],
            0.0,
            ["--value=[0.1,0.2]"],
            (0.1, 0.2),
        ),
        (float | CommaDelimited[tuple[float, ...]], 0.0, ["--value=0.1"], 0.1),
        (
            float | CommaDelimited[tuple[float, ...]],
            0.0,
            ["--value=0.1,0.2"],
            (0.1, 0.2),
        ),
        (float | CommaDelimited[list[float]], 0.0, ["--value=0.1"], 0.1),
        (float | CommaDelimited[list[float]], 0.0, ["--value=0.1,0.2"], [0.1, 0.2]),
        (float | CommaDelimited[list[float]], 0.0, ["--value=[0.1,0.2]"], [0.1, 0.2]),
        (
            float | CommaDelimited[list[float]],
            0.0,
            ["--value", "0.1", "--value", "0.2"],
            [0.1, 0.2],
        ),
        (float | CommaDelimited[set[float]], 0.0, ["--value=0.1"], 0.1),
        (float | CommaDelimited[set[float]], 0.0, ["--value=0.1,0.2"], {0.1, 0.2}),
        (float | CommaDelimited[Sequence[float]], 0.0, ["--value=0.1"], 0.1),
        (
            float | CommaDelimited[Sequence[float]],
            0.0,
            ["--value=0.1,0.2"],
            [0.1, 0.2],
        ),
        (float | SemiColonDelimited[list[float]], 0.0, ["--value=0.1"], 0.1),
        (
            float | SemiColonDelimited[list[float]],
            0.0,
            ["--value=0.1;0.2"],
            [0.1, 0.2],
        ),
        (float | WhitespaceDelimited[list[float]], 0.0, ["--value=0.1"], 0.1),
        (
            float | WhitespaceDelimited[list[float]],
            0.0,
            ["--value=0.1 0.2"],
            [0.1, 0.2],
        ),
        (float | Delimited("|")[list[float]], 0.0, ["--value=0.1"], 0.1),
        (float | Delimited("|")[list[float]], 0.0, ["--value=0.1|0.2"], [0.1, 0.2]),
        (CommaDelimited[list[float]] | None, None, ["--value=null"], None),
        (CommaDelimited[list[float]] | None, None, ["--value=0.1,0.2"], [0.1, 0.2]),
        (float | CommaDelimited[list[float]] | None, None, ["--value=null"], None),
        (float | CommaDelimited[list[float]] | None, None, ["--value=0.1"], 0.1),
        (
            float | CommaDelimited[list[float]] | None,
            None,
            ["--value=0.1,0.2"],
            [0.1, 0.2],
        ),
        (str | CommaDelimited[tuple[str, str]], "a", ["--value=1"], "1"),
        (
            Path | CommaDelimited[tuple[Path, Path]],
            Path("."),
            ["--value=123"],
            Path("123"),
        ),
        (
            _UnionColor | CommaDelimited[tuple[_UnionColor, _UnionColor]],
            _UnionColor.RED,
            ["--value=RED"],
            _UnionColor.RED,
        ),
        (
            _UnionColor | CommaDelimited[tuple[_UnionColor, _UnionColor]],
            _UnionColor.RED,
            ["--value=red,blue"],
            (_UnionColor.RED, _UnionColor.BLUE),
        ),
        (float | Map[dict[str, float]], 0.0, ["--value=0.1"], 0.1),
        (
            float | Map[dict[str, float]],
            0.0,
            ["--value=a=1 b=2"],
            {"a": 1.0, "b": 2.0},
        ),
        (Map[dict[str, float]] | None, None, ["--value=null"], None),
        (
            Map[dict[str, float]] | None,
            None,
            ["--value=a=1 b=2"],
            {"a": 1.0, "b": 2.0},
        ),
        (float | _FloatListAlias, 0.0, ["--value=0.1"], 0.1),
        (float | _FloatListAlias, 0.0, ["--value=0.1,0.2"], [0.1, 0.2]),
    ],
)
def test_delimited_and_map_unions_preserve_scalar_and_delimited_cli_inputs(
    annotation: Any,
    default: Any,
    arguments: list[str],
    expected: Any,
) -> None:
    """Unions mixing scalars or None with Delimited/Map skip premature JSON decoding."""
    settings_cls: Any = type(
        "Settings",
        (BaseConfig,),
        {"__annotations__": {"value": annotation}, "value": default},
        cli_parse_args=True,
    )

    result = settings_cls(_cli_parse_args=arguments)
    assert result.value == expected
    assert type(result.value) is type(expected)


def test_delimited_unions_preserve_scalar_values_from_env_and_dotenv(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Environment and dotenv sources keep raw strings for scalar+Delimited unions."""

    class Settings(BaseConfig, env_prefix="UNION_"):
        text: str | CommaDelimited[tuple[str, str]] = "a"
        color: _UnionColor | CommaDelimited[tuple[_UnionColor, _UnionColor]] = (
            _UnionColor.RED
        )

    monkeypatch.setenv("UNION_TEXT", "1")
    monkeypatch.setenv("UNION_COLOR", "RED")
    from_env = Settings()
    assert from_env.text == "1"
    assert from_env.color is _UnionColor.RED

    monkeypatch.delenv("UNION_TEXT")
    monkeypatch.delenv("UNION_COLOR")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("UNION_TEXT=1\nUNION_COLOR=red,blue\n", encoding="utf-8")
    from_dotenv = Settings(_env_file=dotenv_path)
    assert from_dotenv.text == "1"
    assert from_dotenv.color == (_UnionColor.RED, _UnionColor.BLUE)


def test_union_no_decode_preserves_mixed_complex_branches_and_force_decode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Non-NoDecode complex branches and explicit ForceDecode retain JSON decoding."""

    class Sub(BaseModel):
        x: int = 1

    class Settings(BaseConfig, cli_parse_args=True, env_prefix="MIXED_"):
        sub_union: Sub | CommaDelimited[tuple[int, int]] = Sub()
        dict_union: dict[str, int] | CommaDelimited[list[int]] = Field(
            default_factory=dict
        )
        forced: Annotated[float | CommaDelimited[list[float]], ForceDecode] = 0.0

    assert NoDecode not in Settings.model_fields["sub_union"].metadata
    assert NoDecode not in Settings.model_fields["dict_union"].metadata
    assert NoDecode not in Settings.model_fields["forced"].metadata

    monkeypatch.setenv("MIXED_SUB_UNION", '{"x": 2}')
    assert Settings(_cli_parse_args=[]).sub_union == Sub(x=2)
    monkeypatch.setenv("MIXED_SUB_UNION", "1,2")
    assert Settings(_cli_parse_args=[]).sub_union == (1, 2)
    monkeypatch.delenv("MIXED_SUB_UNION")

    assert Settings(_cli_parse_args=['--dict-union={"x": 2}']).dict_union == {"x": 2}
    assert Settings(_cli_parse_args=["--dict-union=1,2"]).dict_union == [1, 2]
    assert Settings(_cli_parse_args=["--forced=0.1"]).forced == [0.1]


def test_union_no_decode_applies_after_forward_ref_model_rebuild() -> None:
    """Forward-referenced union fields gain NoDecode when model_rebuild completes them."""

    class Settings(BaseConfig, cli_parse_args=True):
        value: "float | DeferredFloatList" = 0.0

    DeferredFloatList = CommaDelimited[list[float]]
    Settings.model_rebuild()

    assert Settings(_cli_parse_args=["--value=0.1"]).value == 0.1
    assert Settings(_cli_parse_args=["--value=0.1,0.2"]).value == [0.1, 0.2]


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


@pytest.mark.parametrize("annotation", [Make, Call], ids=["make", "call"])
def test_directive_factory_values_remain_lazy(annotation: Any) -> None:
    """Repeated validation retains configs without constructing their targets."""
    from confidantic import Factory

    calls: list[int] = []

    class Target:
        def __init__(self, value: int = 1) -> None:
            calls.append(value)
            self.value = value + 1

    config = Factory.instance_from(Target, value=3)
    adapter = TypeAdapter(annotation[Factory[Target]])
    assert adapter.validate_python(config) is config
    assert adapter.validate_python(config) is config
    generated = adapter.validate_python(
        {"@call": Factory.instance_from, "source": Target, "value": 4}
    )
    assert isinstance(generated, Factory)
    assert generated.value == 4
    assert calls == []
    assert config.instance().value == 4
    assert calls == [3]
