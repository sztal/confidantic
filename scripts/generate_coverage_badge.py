"""Generate an SVG badge from a Coverage.py JSON report."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path


def get_badge_color(percentage: float) -> str:
    """Return the badge color for a coverage percentage."""
    if percentage >= 95:
        return "#4c1"
    if percentage >= 90:
        return "#97ca00"
    if percentage >= 80:
        return "#dfb317"
    return "#e05d44"


def format_percentage(percentage: float) -> str:
    """Format a coverage percentage for the badge label."""
    return f"{percentage:.1f}".rstrip("0").rstrip(".") + "%"


def generate_badge(percentage: float) -> str:
    """Return an SVG coverage badge for ``percentage``."""
    label = "coverage"
    value = format_percentage(percentage)
    color = get_badge_color(percentage)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-opacity=".1" stop-color="#fff"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a"><rect width="104" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#a)">
    <path fill="#555" d="M0 0h63v20H0z"/>
    <path fill="{color}" d="M63 0h41v20H63z"/>
    <path fill="url(#b)" d="M0 0h104v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="31.5" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="31.5" y="14">{label}</text>
    <text x="83.5" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="83.5" y="14">{value}</text>
  </g>
</svg>
'''


def get_coverage_percentage(report_path: Path) -> float:
    """Read and validate the total percentage from a Coverage.py JSON report."""
    try:
        report = json.loads(report_path.read_text())
        percentage = report["totals"]["percent_covered"]
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError) as error:
        message = f"invalid coverage report: {report_path}"
        raise ValueError(message) from error

    if not isinstance(percentage, int | float):
        message = f"invalid coverage percentage: {percentage!r}"
        raise ValueError(message)
    return float(percentage)


def create_parser() -> argparse.ArgumentParser:
    """Return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="generate an SVG badge from a Coverage.py JSON report",
    )
    parser.add_argument("report", type=Path, help="path to the coverage JSON report")
    parser.add_argument("output", type=Path, help="path for the generated SVG badge")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate an SVG coverage badge."""
    args = create_parser().parse_args(argv)
    args.output.write_text(generate_badge(get_coverage_percentage(args.report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
