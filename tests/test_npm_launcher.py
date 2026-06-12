from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
import tomllib

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = PACKAGE_ROOT / "package.json"
LAUNCHER = PACKAGE_ROOT / "bin" / "linkedin-apply-assistant.mjs"
PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
INIT_PY = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "__init__.py"
SRC_DIR = PACKAGE_ROOT / "src"
PUBLIC_REPO = "https://github.com/MohammedGhazal09/linkedin-apply-assistant"


def _package_json() -> dict[str, object]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _init_constant(name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']",
        INIT_PY.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, name
    return match.group(1)


def test_package_json_matches_python_identity() -> None:
    package = _package_json()
    pyproject = _pyproject()["project"]

    assert package["name"] == pyproject["name"] == _init_constant("APP_PACKAGE_NAME")
    assert package["version"] == pyproject["version"] == _init_constant("__version__")
    assert package["bin"] == {
        _init_constant("APP_COMMAND_NAME"): "./bin/linkedin-apply-assistant.mjs"
    }
    assert package["license"] == "MIT"
    assert package["type"] == "module"
    assert package["repository"] == {
        "type": "git",
        "url": f"git+{PUBLIC_REPO}.git",
    }
    assert package["homepage"] == f"{PUBLIC_REPO}#readme"
    assert package["bugs"] == {"url": f"{PUBLIC_REPO}/issues"}


def test_package_json_keeps_npm_contents_explicit_and_honest() -> None:
    package = _package_json()
    files = package["files"]

    assert isinstance(files, list)
    assert set(files) == {
        "bin/linkedin-apply-assistant.mjs",
        "README.md",
        "SAFETY.md",
        "LEGAL.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CHANGELOG.md",
        "MIGRATION.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "RELEASE_CHECKLIST.md",
        "docs/commands.md",
        "docs/install-and-configuration.md",
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
    }


def test_package_json_has_no_install_or_publish_automation() -> None:
    package = _package_json()
    scripts = package.get("scripts", {})
    assert isinstance(scripts, dict)

    forbidden_script_names = {
        "preinstall",
        "install",
        "postinstall",
        "prepublish",
        "prepublishOnly",
        "publish",
        "postpublish",
    }
    assert forbidden_script_names.isdisjoint(scripts)

    serialized_scripts = json.dumps(scripts).lower()
    for token in (
        "pip install",
        "python -m pip",
        "pipx install",
        "npm publish",
        "twine upload",
        "pypi publish",
        "npm_token",
        "node_auth_token",
    ):
        assert token not in serialized_scripts


def test_launcher_delegates_to_python_module_without_command_recursion() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "#!/usr/bin/env node" in source
    assert "linkedin_apply_assistant.cli" in source
    assert '"-m", cliModule' in source
    assert "process.argv.slice(2)" in source
    assert 'stdio: "inherit"' in source
    assert 'spawnSync("linkedin-apply-assistant"' not in source
    assert "spawnSync('linkedin-apply-assistant'" not in source


def test_launcher_has_no_hidden_install_or_publish_code() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    code_without_guidance = re.sub(
        r"function printSetupGuidance\(reason\) \{.*?\n\}\n\n",
        "",
        source,
        flags=re.DOTALL,
    ).lower()

    for token in (
        "pip install",
        "python -m pip",
        "pipx install",
        "npm publish",
        "twine upload",
        "pypi publish",
        "npm_token",
        "node_auth_token",
    ):
        assert token not in code_without_guidance


def test_node_launcher_help_delegates_to_python_cli() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is not available; static npm launcher checks still ran")

    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"

    result = subprocess.run(
        ["node", str(LAUNCHER), "--help"],
        cwd=PACKAGE_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "search" in result.stdout
    assert "assist" in result.stdout
    assert "dry-run" in result.stdout
