from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PACKAGE_ROOT / "release-manifest.json"
RELEASE_SCRIPT = PACKAGE_ROOT / "scripts" / "release.py"


def _load_release_module():
    spec = importlib.util.spec_from_file_location("release_script", RELEASE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_has_required_metadata() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["package"] == "linkedin-apply-assistant"
    assert manifest["source_root"] == "."
    assert "files" in manifest
    assert "blocked_patterns" in manifest
    assert "no_publish_scope" in manifest


def test_every_manifest_file_exists() -> None:
    release = _load_release_module()
    files = release.validate_manifest()

    assert files
    for item in files:
        assert (PACKAGE_ROOT / item.path).is_file(), item.path


def test_manifest_includes_tests_and_release_tooling() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}

    assert "tests/test_release_manifest.py" in paths
    assert any(path.startswith("tests/") for path in paths)
    assert "scripts/release.py" in paths
    assert "release-manifest.json" in paths


def test_manifest_includes_phase20_distribution_files_with_narrow_categories() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    categories = {item["path"]: item["category"] for item in manifest["files"]}

    assert categories["package.json"] == "npm-metadata"
    assert categories["bin/linkedin-apply-assistant.mjs"] == "npm-launcher"
    assert categories["pyproject.toml"] == "package-metadata"
    for path in (
        "tests/test_npm_launcher.py",
        "tests/test_distribution_metadata.py",
        "tests/test_distribution_smoke.py",
    ):
        assert categories[path] == "tests"


def test_manifest_includes_phase21_terminal_ux_files_with_narrow_categories() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    categories = {item["path"]: item["category"] for item in manifest["files"]}

    assert categories["docs/commands.md"] == "docs"
    for path in (
        "tests/test_cli_help.py",
        "tests/test_config_diagnostics.py",
    ):
        assert categories[path] == "tests"


def test_manifest_includes_phase26_community_health_files() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    categories = {item["path"]: item["category"] for item in manifest["files"]}

    for path in ("SUPPORT.md", "GOVERNANCE.md", "CODE_OF_CONDUCT.md"):
        assert categories[path] == "docs"

    for path in (
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/docs.yml",
        ".github/ISSUE_TEMPLATE/safety_compliance.yml",
        ".github/ISSUE_TEMPLATE/config_help.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ):
        assert categories[path] == "community-template"

    assert categories["tests/test_community_health.py"] == "tests"


def test_manifest_excludes_private_root_and_runtime_paths() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    forbidden_exact = {
        "cv.md",
        "config/profile.yml",
        "modes/_profile.md",
        "portals.yml",
        "data/applications.md",
    }
    forbidden_root_prefixes = (
        ".planning/",
        "reports/",
        "output/",
    )
    forbidden_fragments = (
        "linkedin_user_data",
        ".env",
    )

    for path in paths:
        assert path not in forbidden_exact
        assert not path.startswith(forbidden_root_prefixes)
        for fragment in forbidden_fragments:
            assert fragment not in path


def test_candidate_materialization_copies_only_manifest_files(tmp_path: Path) -> None:
    release = _load_release_module()
    count = release.copy_candidate(tmp_path)
    manifest_paths = {item.path for item in release.validate_manifest()}
    candidate_paths = {
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()
    }

    assert count == len(manifest_paths)
    assert candidate_paths == manifest_paths
    assert (tmp_path / "pyproject.toml").is_file()
    assert not (tmp_path / ".planning").exists()
    assert not (tmp_path / "reports").exists()


def test_unlisted_live_files_ignore_generated_artifacts() -> None:
    release = _load_release_module()
    unlisted = release.find_unlisted_files(ignore_generated=True)

    assert [path.as_posix() for path in unlisted] == []
