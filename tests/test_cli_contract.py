from __future__ import annotations

from argparse import Namespace
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"
CLI_SOURCE = SRC_DIR / "linkedin_apply_assistant" / "cli.py"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from linkedin_apply_assistant import cli
from linkedin_apply_assistant.contracts import SearchRequest


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "linkedin_apply_assistant.cli", *args],
        cwd=PACKAGE_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_root_help_lists_public_subcommands() -> None:
    result = _run_cli("--help")

    assert result.returncode == 0, result.stderr
    for command in ("search", "assist", "apply", "dry-run", "report", "update"):
        assert command in result.stdout


def test_each_subcommand_help_exits_zero() -> None:
    for command in ("search", "assist", "apply", "dry-run", "report", "update"):
        result = _run_cli(command, "--help")

        assert result.returncode == 0, f"{command}: {result.stderr}"
        assert "usage:" in result.stdout


def test_workspace_option_before_subcommand_is_preserved(tmp_path: Path) -> None:
    result = _run_cli("--workspace", str(tmp_path), "search", "--verbose")

    assert result.returncode == 0, result.stderr
    assert str((tmp_path / "output").resolve()) in result.stdout


def test_workspace_option_after_subcommand_still_works(tmp_path: Path) -> None:
    result = _run_cli("search", "--workspace", str(tmp_path), "--verbose")

    assert result.returncode == 0, result.stderr
    assert str((tmp_path / "output").resolve()) in result.stdout


def test_workspace_relative_config_path_loads(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "config.yml").write_text(
        "profile:\n  name: Example Candidate\npaths:\n  output_dir: local-output\n",
        encoding="utf-8",
    )

    result = _run_cli("search", "--workspace", str(tmp_path), "--config", "configs/config.yml")

    assert result.returncode == 0, result.stderr
    assert "Search complete." in result.stdout


def test_missing_config_path_returns_cli_error_without_traceback() -> None:
    result = _run_cli("search", "--config", "does-not-exist.yml")

    assert result.returncode == 2
    assert "Error: Config file not found:" in result.stderr
    assert "Traceback" not in result.stderr


def test_apply_help_is_approval_gated_and_has_no_legacy_submit_flags() -> None:
    result = _run_cli("apply", "--help")
    help_text = result.stdout
    source_text = CLI_SOURCE.read_text(encoding="utf-8")
    forbidden_terms = (
        "--auto" + "-submit",
        "--un" + "attended",
        "--linkedin" + "-email",
        "--linkedin" + "-password",
    )

    assert result.returncode == 0, result.stderr
    assert any(term in help_text.lower() for term in ("approval", "confirmation", "explicit"))
    for term in forbidden_terms:
        assert term not in help_text
        assert term not in source_text


def test_search_limit_zero_writes_report_without_placeholder_wording(tmp_path: Path) -> None:
    result = _run_cli(
        "search",
        "--workspace",
        str(tmp_path),
        "--search-url",
        "https://www.linkedin.com/jobs/search/?keywords=python&currentJobId=123",
        "--limit",
        "0",
    )
    blocked = "de" + "ferred"

    assert result.returncode == 0, result.stderr
    assert "Search complete." in result.stdout
    assert "Jobs recorded: 0" in result.stdout
    assert "json report:" in result.stdout
    assert blocked not in result.stdout.lower()
    assert any((tmp_path / "output" / "reports").glob("search_*.json"))


def test_search_handler_wires_visible_session_factory_for_live_discovery(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    calls: dict[str, Any] = {}

    class FakeFactory:
        def __init__(self, paths: Any, *, close_on_exit: bool = False) -> None:
            self.paths = paths
            self.close_on_exit = close_on_exit
            calls["factory"] = self

    class FakeDiscovery:
        def __init__(self, session_factory: Any) -> None:
            self.session_factory = session_factory
            calls["discovery"] = self

    def fake_workflow(
        request: SearchRequest,
        discovery: Any,
        report_sink: Any,
        submission_policy: Any = None,
    ) -> Any:
        calls["request"] = request
        calls["discovery_arg"] = discovery
        return type(
            "Result",
            (),
            {
                "summary": {"effective_limit": request.limit},
                "jobs": [],
                "search_url": request.search_url,
                "reports": [],
            },
        )()

    monkeypatch.setattr(cli, "VisibleBrowserSessionFactory", FakeFactory)
    monkeypatch.setattr(cli, "BrowserLinkedInDiscovery", FakeDiscovery)
    monkeypatch.setattr(cli, "run_search_workflow", fake_workflow)

    code = cli._handle_search(
        Namespace(
            workspace=str(tmp_path),
            config=None,
            qa_bank=None,
            browser_profile=None,
            output_dir=None,
            verbose=True,
            query="python",
            location=None,
            search_url=None,
            limit=1,
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Search complete." in output
    assert calls["factory"].close_on_exit is True
    assert calls["factory"].paths.browser_profile_dir == tmp_path / "browser-profile"
    assert calls["discovery"].session_factory is calls["factory"]
    assert calls["discovery_arg"] is calls["discovery"]
    assert calls["request"].limit == 1


def test_apply_confirm_submit_remains_disabled_and_writes_audit(tmp_path: Path) -> None:
    result = _run_cli("apply", "--workspace", str(tmp_path), "--confirm-submit", "--limit", "1")

    assert result.returncode == 0, result.stderr
    assert "Browser submission is disabled" in result.stdout
    assert "remains disabled" in result.stdout
    assert "json report:" in result.stdout
    assert any((tmp_path / "output" / "reports").glob("apply_*.json"))


def test_report_command_summarizes_search_and_assist_payloads(tmp_path: Path) -> None:
    for command in ("search", "assist"):
        report = tmp_path / f"{command}.json"
        report.write_text(
            json.dumps(
                {
                    "command": command,
                    "summary": {"events": 1, "submitted": 0},
                    "jobs": [{"id": "example"}] if command == "search" else [],
                    "events": [{"type": command, "status": "recorded"}],
                }
            ),
            encoding="utf-8",
        )

        result = _run_cli("report", str(report))

        assert result.returncode == 0, result.stderr
        assert "Report summary:" in result.stdout
        assert "submitted: 0" in result.stdout
        assert "events: 1" in result.stdout


def test_dry_run_fixture_validates_three_jobs() -> None:
    fixture = PACKAGE_ROOT / "examples" / "dry_run_input.example.json"

    result = _run_cli("dry-run", "--input", str(fixture))

    assert result.returncode == 0, result.stderr
    assert "Dry run input valid: 3 job(s)" in result.stdout


def test_report_command_prints_summary(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "summary": {"processed": 3, "submitted": 0},
                "jobs": [{"id": "example-1"}, {"id": "example-2"}],
                "events": [{"type": "dry-run"}],
            }
        ),
        encoding="utf-8",
    )

    result = _run_cli("report", str(report))

    assert result.returncode == 0, result.stderr
    assert "Report summary:" in result.stdout
    assert "processed: 3" in result.stdout
    assert "jobs: 2" in result.stdout
    assert "events: 1" in result.stdout


def test_update_check_reports_npm_method_without_running_command(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setenv(cli.INSTALL_CHANNEL_ENV, "npm")

    code = cli.main(["update", "--check"])
    output = capsys.readouterr().out

    assert code == 0
    assert "Current version:" in output
    assert "Update method: npm" in output
    assert "npm install -g linkedin-apply-assistant@latest" in output


def test_update_check_reports_powershell_method_with_install_dir(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setenv(cli.INSTALL_CHANNEL_ENV, "powershell")
    monkeypatch.setenv(cli.INSTALL_DIR_ENV, r"C:\Users\Example\linkedin-apply-assistant")
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: "powershell" if name == "powershell" else None
    )

    code = cli.main(["update", "--check"])
    output = capsys.readouterr().out

    assert code == 0
    assert "Update method: powershell" in output
    assert "install.ps1" in output
    assert "-Update" in output
    assert "-InstallDir 'C:\\Users\\Example\\linkedin-apply-assistant'" in output


def test_update_npm_runs_expected_command(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    def fake_which(name: str) -> str | None:
        return "npm" if name == "npm" else None

    def fake_run(command: list[str], check: bool = False, **_: Any) -> Result:
        calls.append(command)
        assert check is False
        return Result()

    monkeypatch.setenv(cli.INSTALL_CHANNEL_ENV, "npm")
    monkeypatch.setattr(cli.shutil, "which", fake_which)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.main(["update"]) == 0
    assert calls == [["npm", "install", "-g", "linkedin-apply-assistant@latest"]]


def test_update_powershell_runs_expected_command(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    def fake_which(name: str) -> str | None:
        return "pwsh" if name == "pwsh" else None

    def fake_run(command: list[str], check: bool = False, **_: Any) -> Result:
        calls.append(command)
        assert check is False
        return Result()

    monkeypatch.setenv(cli.INSTALL_CHANNEL_ENV, "powershell")
    monkeypatch.setattr(cli.shutil, "which", fake_which)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.main(["update"]) == 0
    assert len(calls) == 1
    assert calls[0][:5] == ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    assert "install.ps1" in calls[0][-1]
    assert "-Update" in calls[0][-1]
