from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from linkedin_apply_assistant.config import load_config
from linkedin_apply_assistant.paths import resolve_runtime_paths


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def test_package_and_cli_imports_have_no_cwd_side_effects(tmp_path: Path) -> None:
    code = "import linkedin_apply_assistant; import linkedin_apply_assistant.cli; print('ok')"

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    browser_profile = "." + "scrapling" + "_browser_profile"
    legacy_browser_profile = "linkedin" + "_user_data"
    legacy_document = "cv" + ".md"
    legacy_output_child = "cvs"
    forbidden_paths = (
        tmp_path / legacy_browser_profile,
        tmp_path / "output",
        tmp_path / "reports",
        tmp_path / "config" / "profile.yml",
        tmp_path / browser_profile,
        tmp_path / legacy_document,
        tmp_path / "output" / legacy_output_child,
        tmp_path / "browser-profile",
    )
    for path in forbidden_paths:
        assert not path.exists(), f"unexpected import side effect: {path}"


def test_workspace_runtime_paths_are_resolved_without_creating_directories(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)

    assert paths.workspace == tmp_path.resolve()
    assert paths.config_dir == tmp_path / "configs"
    assert paths.data_dir == tmp_path / "data"
    assert paths.cache_dir == tmp_path / ".cache"
    assert paths.config_file == tmp_path / "configs" / "config.yml"
    assert paths.qa_bank_file == tmp_path / "configs" / "qa_bank.yml"
    assert paths.browser_profile_dir == tmp_path / "browser-profile"
    assert paths.output_dir == tmp_path / "output"
    assert paths.reports_dir == tmp_path / "output" / "reports"

    for path in (
        paths.config_dir,
        paths.data_dir,
        paths.cache_dir,
        paths.config_file,
        paths.qa_bank_file,
        paths.browser_profile_dir,
        paths.output_dir,
        paths.reports_dir,
    ):
        assert not path.exists(), f"resolver should not create {path}"


def test_default_config_has_no_required_file_or_credentials() -> None:
    config = load_config()

    assert config.profile == {}
    assert config.defaults == {}
    assert config.raw == {}
    assert config.runtime is not None
