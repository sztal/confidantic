"""Shared type-checking scope, levels, and validation failure policy."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from mypy.main import process_options

import noxfile
from scripts import typecheck


@pytest.fixture
def policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[tool.project-checks]\ntypecheck_level = "basic"\n'
        "typecheck_source_only = true\nrequire_typecheck = true\n"
    )
    monkeypatch.setattr(typecheck, "PYPROJECT", path)
    return path


@pytest.mark.parametrize("level", ["none", "basic", "strict"])
def test_level_controls_effective_mypy_options(policy: Path, level: str) -> None:
    policy.write_text(policy.read_text().replace('"basic"', f'"{level}"'))
    flags = typecheck.mypy_args()
    if level == "none":
        assert flags is None
        return
    _, options = process_options(
        ["--config-file", str(policy), *flags, "src/confidantic"]
    )
    assert options.disallow_untyped_defs is (level == "strict")
    assert options.disallow_untyped_calls is (level == "strict")
    assert options.warn_return_any is (level == "strict")
    if level == "strict":
        assert options.warn_unreachable
        assert "ignore-without-code" in options.enable_error_code


@pytest.mark.parametrize("source_only", [True, False])
def test_scope_is_explicitly_opt_in(policy: Path, source_only: bool) -> None:
    policy.write_text(
        policy.read_text().replace(
            "typecheck_source_only = true",
            f"typecheck_source_only = {str(source_only).lower()}",
        )
    )
    assert typecheck.mypy_paths() == (
        ["src/confidantic"]
        if source_only
        else ["src/confidantic", "tests", "scripts", "noxfile.py"]
    )


@pytest.mark.parametrize(
    "original,replacement",
    [
        ('typecheck_level = "basic"', 'typecheck_level = "unknown"'),
        ('typecheck_level = "basic"', "typecheck_level = false"),
        ('typecheck_level = "basic"', ""),
        ("require_typecheck = true", 'require_typecheck = "true"'),
        ("typecheck_source_only = true", "typecheck_source_only = 1"),
        ("[tool.project-checks]", "[tool.other]"),
    ],
)
def test_invalid_policy_never_runs_commands(
    policy: Path, monkeypatch: pytest.MonkeyPatch, original: str, replacement: str
) -> None:
    policy.write_text(policy.read_text().replace(original, replacement))
    run = Mock()
    monkeypatch.setattr(typecheck.subprocess, "run", run)
    with pytest.raises(ValueError, match="type-checking settings"):
        typecheck.main(["--policy"])
    run.assert_not_called()


@pytest.mark.parametrize("required", [True, False])
@pytest.mark.parametrize("policy_mode", [True, False])
@pytest.mark.parametrize("fail", [True, False])
def test_failure_policy(
    policy: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    required: bool,
    policy_mode: bool,
    fail: bool,
) -> None:
    policy.write_text(
        policy.read_text().replace(
            "require_typecheck = true", f"require_typecheck = {str(required).lower()}"
        )
    )
    run = Mock(
        side_effect=subprocess.CalledProcessError(1, ["make", "_typecheck"])
        if fail
        else None
    )
    monkeypatch.setattr(typecheck.subprocess, "run", run)
    argv = ["--policy"] if policy_mode else []
    if fail and (required or not policy_mode):
        with pytest.raises(subprocess.CalledProcessError):
            typecheck.main(argv)
    else:
        typecheck.main(argv)
    run.assert_called_once_with(["make", "_typecheck"], cwd=policy.parent, check=True)
    assert ("not required" in capsys.readouterr().err) is (
        fail and policy_mode and not required
    )


def test_disabled_check_skips_execution(
    policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    policy.write_text(policy.read_text().replace('"basic"', '"none"'))
    run = Mock()
    monkeypatch.setattr(typecheck.subprocess, "run", run)
    typecheck.main([])
    typecheck.main(["--policy"])
    run.assert_not_called()
    assert "disabled" in capsys.readouterr().out
    session = Mock(posargs=[], skip=Mock(side_effect=RuntimeError("disabled")))
    with pytest.raises(RuntimeError, match="disabled"):
        noxfile.typecheck(session)
    session.install.assert_not_called()
    session.run.assert_not_called()


@pytest.mark.parametrize("posargs", [[], ["tests/scripts", "--show-error-codes"]])
def test_nox_uses_policy_and_preserves_explicit_overrides(
    policy: Path, posargs: list[str]
) -> None:
    policy.write_text(
        policy.read_text()
        .replace('"basic"', '"strict"')
        .replace("typecheck_source_only = true", "typecheck_source_only = false")
    )
    session = Mock(posargs=posargs)
    noxfile.typecheck(session)
    command = session.run.call_args.args
    assert command[0] == "mypy"
    assert "--strict" in command
    paths = posargs or ["src/confidantic", "tests", "scripts", "noxfile.py"]
    assert list(command[-len(paths) :]) == paths


def test_repository_defaults_check_only_package_without_strict_mode() -> None:
    assert typecheck.settings() == ("basic", True, True)
    sources, options = process_options(
        ["--config-file", str(typecheck.PYPROJECT), *typecheck.mypy_paths()]
    )
    assert sources
    assert all(
        Path(source.path).parts[:2] == ("src", "confidantic") for source in sources
    )
    assert not options.disallow_untyped_defs
    assert not options.disallow_untyped_calls
    assert not options.disallow_any_generics
    assert not options.warn_return_any
    assert options.warn_unreachable
