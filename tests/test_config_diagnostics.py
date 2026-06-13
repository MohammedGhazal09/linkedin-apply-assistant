from __future__ import annotations

import builtins
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def _cli_module() -> Any:
    from linkedin_apply_assistant import cli

    return cli


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "linkedin_apply_assistant.cli", *args],
        cwd=PACKAGE_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_config_check_reports_paths_without_creating_files(tmp_path: Path) -> None:
    result = _run_cli("config", "check", "--workspace", str(tmp_path))
    output = result.stdout.lower()

    assert result.returncode == 0, result.stderr
    for phrase in (
        "config diagnostics",
        "no files or directories were created",
        "missing",
        "warning",
        "config file",
        "q&a bank",
        "browser profile",
        "output directory",
        "reports directory",
        "data directory",
        "cache directory",
        "configs/config.example.yml",
        "configs/qa_bank.example.yml",
        "answer truthfully",
        "python -m playwright install chromium",
    ):
        assert phrase in output

    for path in (
        tmp_path / "configs",
        tmp_path / "data",
        tmp_path / ".cache",
        tmp_path / "browser-profile",
        tmp_path / "output",
        tmp_path / "configs" / "config.yml",
        tmp_path / "configs" / "qa_bank.yml",
    ):
        assert not path.exists(), f"config check created {path}"


def test_config_shorthand_defaults_to_check_without_creating_files(tmp_path: Path) -> None:
    result = _run_cli("--verbose", "config", "--workspace", str(tmp_path))
    output = result.stdout.lower()

    assert result.returncode == 0, result.stderr
    assert "config diagnostics" in output
    assert "no files or directories were created" in output
    assert "the following arguments are required" not in result.stderr

    for path in (
        tmp_path / "configs",
        tmp_path / "data",
        tmp_path / ".cache",
        tmp_path / "browser-profile",
        tmp_path / "output",
    ):
        assert not path.exists(), f"config shorthand created {path}"


def test_browser_free_commands_work_without_config_or_browser_setup(tmp_path: Path) -> None:
    dry_run = _run_cli(
        "dry-run", "--input", str(PACKAGE_ROOT / "examples" / "dry_run_input.example.json")
    )

    assert dry_run.returncode == 0, dry_run.stderr
    assert "Dry run input valid" in dry_run.stdout

    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"summary": {"submitted": 0}, "jobs": [], "events": []}),
        encoding="utf-8",
    )
    report = _run_cli("report", str(report_path))

    assert report.returncode == 0, report.stderr
    assert "Report summary:" in report.stdout


def test_missing_explicit_config_has_actionable_error(tmp_path: Path) -> None:
    result = _run_cli("search", "--config", str(tmp_path / "missing.yml"))

    assert result.returncode == 2
    assert "Error: Config file not found:" in result.stderr
    assert "Try: linkedin-apply-assistant config check" in result.stderr
    assert "Traceback" not in result.stderr


def test_invalid_explicit_config_has_actionable_error(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    result = _run_cli("search", "--config", str(config_path))

    assert result.returncode == 2
    assert "Error: Invalid config:" in result.stderr
    assert "Try: linkedin-apply-assistant config check" in result.stderr
    assert "Traceback" not in result.stderr


def test_invalid_json_errors_are_traceback_free(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")

    result = _run_cli("dry-run", "--input", str(bad_json))

    assert result.returncode == 2
    assert "Error: Invalid JSON" in result.stderr
    assert "Try: check the --input path and JSON format." in result.stderr
    assert "Traceback" not in result.stderr


def test_search_browser_failure_uses_cli_error_contract(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    cli = _cli_module()

    def fail_workflow(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "Browser setup failed: Chromium could not be launched.\n"
            "Try: python -m playwright install chromium\n"
            f"Browser profile: {tmp_path / 'browser-profile'}"
        )

    monkeypatch.setattr(cli, "run_search_workflow", fail_workflow)

    code = cli.main(
        [
            "search",
            "--workspace",
            str(tmp_path),
            "--query",
            "python",
            "--limit",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert "Error: Browser setup failed" in captured.err
    assert "python -m playwright install chromium" in captured.err
    assert "Browser profile:" in captured.err
    assert "Traceback" not in captured.err


def test_visible_browser_factory_missing_playwright_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from linkedin_apply_assistant.browser_sessions import VisibleBrowserSessionFactory
    from linkedin_apply_assistant.paths import resolve_runtime_paths

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "playwright.sync_api":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    paths = resolve_runtime_paths(workspace=tmp_path)
    factory = VisibleBrowserSessionFactory(paths)

    with pytest.raises(RuntimeError) as exc_info:
        factory.open(object())

    message = str(exc_info.value)
    assert "Browser setup failed" in message
    assert "python -m playwright install chromium" in message
    assert str(paths.browser_profile_dir) in message


def test_assist_warns_about_missing_qa_bank_before_browser_work(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    cli = _cli_module()

    def fake_assist_workflow(*args: Any, **kwargs: Any) -> Any:
        return type(
            "Result",
            (),
            {
                "summary": {
                    "mode": "on-demand",
                    "events": 0,
                    "filled": 0,
                    "blocked": 0,
                    "submitted": 0,
                },
                "events": [],
                "reports": [],
            },
        )()

    monkeypatch.setattr(cli, "run_assist_workflow", fake_assist_workflow)

    code = cli.main(["assist", "--workspace", str(tmp_path), "--mode", "on-demand"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Warning: Q&A bank is missing:" in captured.out
    assert "configs/qa_bank.example.yml" in captured.out
    assert "answer truthfully" in captured.out
