"""Tests for the coverage badge generator."""

import json
from pathlib import Path

import pytest

from scripts.generate_coverage_badge import (
    generate_badge,
    get_badge_color,
    get_coverage_percentage,
)


@pytest.mark.parametrize(
    ("percentage", "color"),
    [
        (95, "#4c1"),
        (90, "#97ca00"),
        (80, "#dfb317"),
        (79.9, "#e05d44"),
    ],
)
def test_get_badge_color_uses_coverage_thresholds(
    percentage: float,
    color: str,
) -> None:
    """Coverage thresholds use recognizable badge colors."""
    assert get_badge_color(percentage) == color


def test_generate_badge_includes_formatted_percentage_and_color() -> None:
    """The generated SVG shows the percentage and its threshold color."""
    badge = generate_badge(95.25)

    assert 'aria-label="coverage: 95.2%"' in badge
    assert 'fill="#4c1"' in badge


def test_get_coverage_percentage_reads_coverage_json(tmp_path: Path) -> None:
    """The Coverage.py total is read from the JSON report."""
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"totals": {"percent_covered": 96.7}}))

    assert get_coverage_percentage(report_path) == 96.7


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"totals": {}},
        {"totals": {"percent_covered": "96.7"}},
    ],
)
def test_get_coverage_percentage_rejects_invalid_reports(
    tmp_path: Path,
    report: object,
) -> None:
    """Malformed or incomplete coverage reports fail clearly."""
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(report))

    with pytest.raises(ValueError):
        get_coverage_percentage(report_path)


def test_get_coverage_percentage_rejects_missing_report(tmp_path: Path) -> None:
    """A missing coverage report fails clearly."""
    with pytest.raises(ValueError):
        get_coverage_percentage(tmp_path / "coverage.json")
