# Test suite

The test layout follows the source layout. Private source module names omit their
leading underscore after the `test_` prefix: `_config/_settings.py` maps to
`tests/_config/test_settings.py`.

| Source or behavior                                                                  | Test location                       |
| ----------------------------------------------------------------------------------- | ----------------------------------- |
| `confidantic/__init__.py`                                                           | `test_init.py`                      |
| `confidantic/annotations.py`, `context.py`, `paths.py`, and other top-level modules | Corresponding `test_<module>.py`    |
| `confidantic/_config/`                                                              | Corresponding modules in `_config/` |
| Fresh-process imports, optional dependencies, serialization, and runnable examples  | `integration/`                      |
| Repository maintenance scripts                                                      | Corresponding modules in `scripts/` |

Place regressions beside the behavior they protect, rather than in a separate
audit or regression module. Tests for private modules should exercise observable
behavior through public APIs where practical. Cross-module tests belong in
`integration/` when no single source module owns the behavior.

Reusable importable targets and configuration models live in `_config/factory_targets.py`
and `_config/models.py`. Keep helpers local unless multiple test modules need
them, and avoid importing fixtures or models from another test module. Import
identifiers in serialization assertions must continue to name importable objects.
`helpers.py` provides isolated Python execution with bounded runtime and captured
diagnostics. Use it for checks that change process-wide logging or import state.

Run the full suite after linting:

```console
uv run noxfile.py -s lint
uv run pytest
```

To focus on one area, pass its path to pytest, for example
`uv run pytest tests/_config/test_nested.py`. The full run also collects package
and documentation doctests. Example coverage is listed in
`integration/test_examples.py`.

For coverage statistics, erase old data before `make coverage`, especially after
moving files. Confirmed unresolved source defects belong in the repository's
`BUGS.md`; a test audit records them without changing package behavior.
Expected-failure tests name the relevant bug, use strict markers, and include
passing controls where practical so a fix cannot silently leave stale markers.
