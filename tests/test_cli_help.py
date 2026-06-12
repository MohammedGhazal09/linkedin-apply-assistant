from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"
CLI_SOURCE = SRC_DIR / "linkedin_apply_assistant" / "cli.py"


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


def _assert_help(*args: str) -> str:
    result = _run_cli(*args, "--help")

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    return result.stdout


def test_root_help_includes_first_run_safety_and_outputs() -> None:
    help_text = _assert_help()
    lower_text = help_text.lower()

    for command in ("config", "search", "assist", "apply", "dry-run", "report"):
        assert command in lower_text
    for phrase in (
        "config check",
        "python -m playwright install chromium",
        "output directory",
        "reports",
        "no-submit",
        "fill-only",
        "browser submission remains disabled",
    ):
        assert phrase in lower_text


def test_config_help_describes_read_only_diagnostics() -> None:
    config_help = _assert_help("config")
    check_help = _assert_help("config", "check")
    combined = f"{config_help}\n{check_help}".lower()

    for phrase in (
        "read-only",
        "config",
        "q&a bank",
        "browser profile",
        "output",
        "reports",
        "data",
        "cache",
        "no files",
        "no directories",
    ):
        assert phrase in combined


def test_browser_command_help_includes_examples_safety_and_setup() -> None:
    expectations = {
        "search": ("examples:", "config check", "reports", "no-submit"),
        "assist": (
            "examples:",
            "python -m playwright install chromium",
            "browser-profile",
            "fill-only",
            "no-submit",
        ),
        "apply": (
            "examples:",
            "prepare-only",
            "browser submission remains disabled",
            "reports",
            "no-submit",
        ),
    }

    for command, phrases in expectations.items():
        help_text = _assert_help(command).lower()
        for phrase in phrases:
            assert phrase in help_text, f"{command}: {phrase}"


def test_browser_free_help_includes_concise_examples() -> None:
    for command in ("dry-run", "report"):
        help_text = _assert_help(command).lower()

        assert "example:" in help_text
        assert "browser-free" in help_text
        assert (
            "does not require config" in help_text or "reads an existing local report" in help_text
        )


def test_help_does_not_introduce_legacy_unsafe_flags() -> None:
    source_text = CLI_SOURCE.read_text(encoding="utf-8")
    help_texts = [
        _assert_help(),
        _assert_help("search"),
        _assert_help("assist"),
        _assert_help("apply"),
        _assert_help("config", "check"),
    ]
    combined = "\n".join(help_texts + [source_text])
    forbidden_flags = (
        "--auto" + "-submit",
        "--un" + "attended",
        "--linkedin" + "-email",
        "--linkedin" + "-password",
    )

    for flag in forbidden_flags:
        assert flag not in combined
