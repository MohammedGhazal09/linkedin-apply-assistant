from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
QUALITY_SCRIPT = PACKAGE_ROOT / "scripts" / "quality.py"


def _load_quality_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quality", QUALITY_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_gate_order_and_commands_are_explicit() -> None:
    quality = _load_quality_module()
    gates = quality.build_gates()

    assert [gate.name for gate in gates] == [
        "compile",
        "pytest",
        "ruff check",
        "ruff format",
        "dependency audit",
    ]
    assert [gate.display_command for gate in gates] == [
        "python -m compileall -q src tests",
        "python -m pytest tests -q",
        "python -m ruff check --no-cache src tests",
        "python -m ruff format --check --no-cache src tests",
        "python -m pip_audit --requirement <installed-dev-dependency-closure> --no-deps --progress-spinner off",
    ]


def test_quality_gate_list_mode_prints_without_running(capsys) -> None:
    quality = _load_quality_module()

    assert quality.main(["--list"]) == 0

    output = capsys.readouterr().out
    for expected in (
        "compile: python -m compileall -q src tests",
        "pytest: python -m pytest tests -q",
        "ruff check: python -m ruff check --no-cache src tests",
        "ruff format: python -m ruff format --check --no-cache src tests",
        "dependency audit: python -m pip_audit --requirement <installed-dev-dependency-closure> --no-deps --progress-spinner off",
    ):
        assert expected in output


def test_quality_gate_does_not_enable_live_or_private_root_scope() -> None:
    quality = _load_quality_module()
    command_text = "\n".join(gate.display_command for gate in quality.build_gates())

    assert "CAREER_OPS_RUN_LIVE_TESTS" not in command_text
    assert "linkedin" + "_user_data" not in command_text
    assert "cv" + ".md" not in command_text
    assert "config" + "/" + "profile" + ".yml" not in command_text
    assert "data" + "/" + "applications" + ".md" not in command_text


def test_dependency_audit_covers_installed_dev_dependency_closure() -> None:
    quality = _load_quality_module()

    pins = quality.build_installed_dependency_pins()

    package_names = {pin.split("==", 1)[0].lower() for pin in pins}
    assert "pytest" in package_names
    assert "ruff" in package_names
    assert "pip-audit" in package_names
    assert "playwright" in package_names
    assert "scrapling" in package_names
    assert "linkedin-apply-assistant" not in package_names


def test_dependency_audit_uses_isolated_cache_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    quality = _load_quality_module()
    requirements_file = tmp_path / "audit-requirements.txt"
    requirements_file.write_text("pytest==9.0.3\n", encoding="utf-8")
    monkeypatch.setattr(quality, "write_audit_requirements", lambda: requirements_file)

    command, display_command, cleanup_paths = quality.prepare_gate_command(
        quality.build_gates()[-1]
    )

    assert "--cache-dir" in command
    cache_dir = Path(command[command.index("--cache-dir") + 1])
    assert cache_dir.is_dir()
    assert str(cache_dir) in display_command
    assert cleanup_paths == (requirements_file, cache_dir)

    for path in cleanup_paths:
        quality._cleanup_temp_path(path)
    assert not requirements_file.exists()
    assert not cache_dir.exists()
