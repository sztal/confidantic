.PHONY: help clean build wheel install test coverage coverage-html lint format docs docs-serve init nox check check-dist merge-check merge release-notes release publish

# Export user input as data, never interpolate it into shell source.
export BRANCH NOTES NO_NOTES_REASON VERSION TAG


help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help           Show this help message"
	@echo "  clean          Remove build artifacts and cache files"
	@echo "  build          Build source distribution and wheel"
	@echo "  wheel          Build wheel only"
	@echo "  install        Install the package with development dependencies"
	@echo "  test           Run the pytest suite"
	@echo "  coverage       Run tests with a terminal coverage report"
	@echo "  coverage-html  Run tests with an HTML coverage report"
	@echo "  lint           Run pre-commit checks"
	@echo "  format         Format Python files with Ruff"
	@echo "  docs           Build documentation into site/ (clean and strict)"
	@echo "  docs-serve     Preview documentation with automatic reload"
	@echo "  check          Lint, test, typecheck, docs, build, and check distributions"
	@echo "  check-dist     Check dist/; optionally require TAG=vX.Y.Z"
	@echo "  merge-check    Rehearse BRANCH with NOTES or NO_NOTES_REASON"
	@echo "  merge          Validate and merge BRANCH into local master"
	@echo "  release-notes  Preview notes for VERSION=X.Y.Z"
	@echo "  release        Prepare VERSION locally; no push or publication"
	@echo "  publish        Explicitly publish remote TAG through GitHub Actions"

init:
	make install
	pre-commit install

clean:
	rm -rf dist/ build/ .nox/ .pytest_cache/ .ruff_cache/ htmlcov/
	find . -name "*.egg-info" -type d -prune -exec rm -rf {} +
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.py[cod]" -delete
	find . -name ".coverage*" -delete

build:
	uv run python -m scripts.distributions build

wheel:
	uv build --no-sources --wheel

install:
	uv sync --group dev

nox:
	uv run nox -s tests

test:
	uv run pytest

coverage:
	uv run coverage run -m pytest
	uv run coverage report

coverage-html:
	uv run coverage run -m pytest
	uv run coverage html

lint:
	uv run noxfile.py -s lint

format:
	uv run ruff format .

docs:
	uv run noxfile.py -s docs

docs-serve:
	uv run noxfile.py -s autodocs

check:
	uv run python -m scripts.check

check-dist:
	uv run --locked --group release python -m scripts.commands check-dist

merge-check:
	uv run python -m scripts.commands merge-check

merge:
	uv run python -m scripts.commands merge

release-notes:
	uv run --locked --group release python -m scripts.commands release-notes

release:
	uv run --locked --group release python -m scripts.commands release

publish:
	uv run --locked --group release python -m scripts.commands publish
