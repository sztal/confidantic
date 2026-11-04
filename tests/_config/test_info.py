"""Configuration tables and rendered output through the public display API."""

from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from pydantic import (
    BaseModel,
    Field,
    SecretStr,
)
from rich.console import Console
from rich.table import Table

from confidantic import BaseConfig


def _render_with_colors(table: Table) -> str:
    buffer = StringIO()
    Console(
        file=buffer,
        color_system="standard",
        force_terminal=True,
    ).print(table)
    return buffer.getvalue()


def test_model_info_builds_table_without_evaluating_factories(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Model metadata renders without constructing default values."""
    factory_calls = 0

    def make_values() -> list[str]:
        nonlocal factory_calls
        factory_calls += 1
        return ["generated"]

    class ParentConfig(BaseConfig):
        inherited: int = 1

    class Config(ParentConfig):
        required: str
        aliased: list[str] = Field(
            default_factory=make_values,
            alias="ALIASED",
            description="[bold]Literal description[/bold]",
        )
        optional: str | None = None

    table = Config.model_info(output="table")

    assert isinstance(table, Table)
    assert table.title == "Config"
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Default",
        "Description",
    ]
    assert len(table.rows) == 4
    assert factory_calls == 0

    rendered = Config.model_info(output="string")

    assert capsys.readouterr().out == ""
    assert "\x1b[" not in rendered
    assert rendered.endswith("\n")
    assert rendered.index("inherited") < rendered.index("required")
    assert "aliased" in rendered
    assert "ALIASED" not in rendered
    assert "list[str]" in rendered
    assert "required" in rendered
    assert "<factory: make_values>" in rendered
    assert "None" in rendered
    assert "[bold]Literal" in rendered
    assert "description[/bold]" in rendered
    assert factory_calls == 0


def test_model_info_controls_header_and_description() -> None:
    """Header and description controls alter only their table features."""

    class Config(BaseConfig):
        value: str = Field("default", description="The value.")

    table = Config.model_info(output="table", header=False, describe=False)

    assert table.title is None
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Default",
    ]


def test_model_info_controls_colors() -> None:
    """Colors are disabled by default and enabled only when requested."""

    class Config(BaseConfig):
        required: str
        number: int = 1

    plain_table = Config.model_info(output="table")
    colored_table = Config.model_info(output="table", colors=True)

    assert not plain_table.columns[0].style
    assert colored_table.columns[0].style == "cyan"
    assert "\x1b[" not in _render_with_colors(plain_table)
    assert "\x1b[" in _render_with_colors(colored_table)
    assert "\x1b[" not in Config.model_info(output="string")
    assert "\x1b[" in Config.model_info(output="string", colors=True)


def test_model_info_prints_by_default_and_validates_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default mode prints, while unsupported modes fail clearly."""

    class Config(BaseConfig):
        value: str = "default"

    assert Config.model_info() is None
    printed = capsys.readouterr().out
    assert "Config" in printed
    assert "\x1b[" not in printed

    assert Config.model_info(colors=True) is None
    assert "\x1b[" in capsys.readouterr().out

    invalid_output: Any = "invalid"
    with pytest.raises(ValueError, match="Invalid output mode: 'invalid'"):
        Config.model_info(output=invalid_output)


def test_info_shows_actual_values_without_evaluating_factories_again(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Instance information preserves current Python values and masked secrets."""
    factory_calls = 0

    class Status(Enum):
        ready = "ready"

    class Options(BaseModel):
        enabled: bool

    def make_values() -> list[int]:
        nonlocal factory_calls
        factory_calls += 1
        return [1, 2]

    class Config(BaseConfig):
        name: str = Field("default", alias="NAME", description="The name.")
        status: Status = Status.ready
        path: Path = Path("/d")
        options: Options = Options(enabled=False)
        values: list[int] = Field(default_factory=make_values)
        secret: SecretStr = SecretStr("default-secret")

    config = Config(
        NAME="current",
        path=Path("/x"),
        options=Options(enabled=True),
        secret=SecretStr("actual-secret"),
    )
    assert factory_calls == 1

    table = config.info(output="table")

    assert isinstance(table, Table)
    assert table.title == "Config"
    assert [column.header for column in table.columns] == [
        "Option",
        "Value",
        "Description",
    ]
    assert len(table.rows) == 6

    rendered = config.info(output="string", describe=False)

    assert capsys.readouterr().out == ""
    assert "NAME" not in rendered
    assert "'current'" in rendered
    assert "'default'" not in rendered
    assert "Status.ready" in rendered
    assert "PosixPath('/x')" in rendered
    assert "Options(enabled=True)" in rendered
    assert "[1, 2]" in rendered
    assert "actual-secret" not in rendered
    assert "default-secret" not in rendered
    assert "**********" in rendered
    assert "The name." in config.info(output="string")
    assert factory_calls == 1


def test_info_controls_table_and_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Instance information mirrors model display and output controls."""

    class Config(BaseConfig):
        value: str = "default"

    config = Config(value="current")
    plain_table = config.info(output="table")
    table = config.info(
        output="table",
        header=False,
        describe=False,
        colors=True,
        types=True,
    )

    assert table.title is None
    assert [column.header for column in table.columns] == [
        "Option",
        "Type",
        "Value",
    ]
    assert table.columns[0].style == "cyan"
    assert "\x1b[" not in _render_with_colors(plain_table)
    assert "\x1b[" in _render_with_colors(table)
    assert "\x1b[" not in config.info(output="string")
    assert "\x1b[" in config.info(output="string", colors=True)
    assert capsys.readouterr().out == ""

    assert config.info() is None
    assert "\x1b[" not in capsys.readouterr().out

    invalid_output: Any = "invalid"
    with pytest.raises(ValueError, match="Invalid output mode: 'invalid'"):
        config.info(output=invalid_output)
