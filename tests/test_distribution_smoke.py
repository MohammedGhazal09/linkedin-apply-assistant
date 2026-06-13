from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BLOCKED_NPM_PREFIXES = (
    ".planning/",
    "data/",
    "output/",
    "reports/",
    "browser-profile/",
    "linkedin_" + "user_data",
)


def test_python_build_creates_sdist_and_wheel_without_root_artifacts(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(tmp_path)],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    cleanup = subprocess.run(
        [sys.executable, "scripts/release.py", "clean"],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr
    assert any(path.suffix == ".whl" for path in tmp_path.iterdir())
    assert any(path.name.endswith(".tar.gz") for path in tmp_path.iterdir())

    for relative_path in ("build", "dist", "src/linkedin_apply_assistant.egg-info"):
        assert not (PACKAGE_ROOT / relative_path).exists(), relative_path


def test_npm_pack_dry_run_reports_expected_public_files() -> None:
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm is not available; package.json and launcher static tests still ran")

    result = subprocess.run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload

    files = {item["path"] for item in payload[0]["files"]}
    expected = {
        "package.json",
        "bin/linkedin-apply-assistant.mjs",
        "pyproject.toml",
        "install.ps1",
        "README.md",
        "SAFETY.md",
        "LEGAL.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CHANGELOG.md",
        "MIGRATION.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "GOVERNANCE.md",
        "CODE_OF_CONDUCT.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/docs.yml",
        ".github/ISSUE_TEMPLATE/safety_compliance.yml",
        ".github/ISSUE_TEMPLATE/config_help.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "RELEASE_CHECKLIST.md",
        "docs/commands.md",
        "docs/ci-and-release-policy.md",
        "docs/install-and-configuration.md",
        "docs/registry-publication-strategy.md",
        "docs/browser-session.md",
        "docs/search.md",
        "docs/assist.md",
        "docs/apply.md",
        "docs/reports.md",
        "docs/troubleshooting.md",
        "configs/config.example.yml",
        "configs/qa_bank.example.yml",
        "examples/dry_run_input.example.json",
        "examples/reports/search-report.example.json",
        "examples/reports/apply-audit.example.json",
        "src/linkedin_apply_assistant/__init__.py",
        "src/linkedin_apply_assistant/cli.py",
        "src/linkedin_apply_assistant/workflows.py",
    }
    assert expected.issubset(files)

    for path in files:
        assert not any(path.startswith(prefix) for prefix in BLOCKED_NPM_PREFIXES)
        assert ".env" not in path
        assert "__pycache__" not in path
        assert not path.endswith(".egg-info")
