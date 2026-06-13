from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
PACKAGE_JSON = PACKAGE_ROOT / "package.json"
INIT_PY = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "__init__.py"
CHANGELOG = PACKAGE_ROOT / "CHANGELOG.md"
RELEASE_CHECKLIST = PACKAGE_ROOT / "RELEASE_CHECKLIST.md"
README = PACKAGE_ROOT / "README.md"
INSTALL_DOC = PACKAGE_ROOT / "docs" / "install-and-configuration.md"
REGISTRY_STRATEGY_DOC = PACKAGE_ROOT / "docs" / "registry-publication-strategy.md"
PUBLIC_REPO = "https://github.com/MohammedGhazal09/linkedin-apply-assistant"
NPM_REPOSITORY = f"git+{PUBLIC_REPO}.git"
HOMEPAGE = f"{PUBLIC_REPO}#readme"
ISSUES = f"{PUBLIC_REPO}/issues"


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _package_json() -> dict[str, object]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _init_constant(name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']",
        INIT_PY.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, name
    return match.group(1)


def test_python_and_npm_package_identity_stays_synchronized() -> None:
    pyproject_project = _pyproject()["project"]
    package = _package_json()

    assert pyproject_project["name"] == "linkedin-apply-assistant"
    assert pyproject_project["version"] == "0.1.3"
    assert package["version"] == "0.1.3"
    assert package["name"] == pyproject_project["name"]
    assert package["version"] == pyproject_project["version"]
    assert _init_constant("__version__") == pyproject_project["version"]
    assert _init_constant("APP_PACKAGE_NAME") == pyproject_project["name"]
    assert _init_constant("APP_IMPORT_NAME") == "linkedin_apply_assistant"
    assert _init_constant("APP_COMMAND_NAME") == "linkedin-apply-assistant"


def test_command_and_launcher_metadata_stays_synchronized() -> None:
    pyproject_project = _pyproject()["project"]
    package = _package_json()

    assert pyproject_project["scripts"] == {
        "linkedin-apply-assistant": "linkedin_apply_assistant.cli:main"
    }
    assert package["bin"] == {"linkedin-apply-assistant": "bin/linkedin-apply-assistant.mjs"}
    assert (PACKAGE_ROOT / "bin" / "linkedin-apply-assistant.mjs").is_file()


def test_build_tool_is_declared_for_distribution_verification() -> None:
    optional_deps = _pyproject()["project"]["optional-dependencies"]
    dev_deps = optional_deps["dev"]

    assert any(dep.startswith("build>=") for dep in dev_deps)


def test_distribution_docs_and_release_surfaces_include_identity() -> None:
    docs = {
        "README.md": README.read_text(encoding="utf-8"),
        "docs/install-and-configuration.md": INSTALL_DOC.read_text(encoding="utf-8"),
        "docs/registry-publication-strategy.md": REGISTRY_STRATEGY_DOC.read_text(encoding="utf-8"),
        "CHANGELOG.md": CHANGELOG.read_text(encoding="utf-8"),
        "RELEASE_CHECKLIST.md": RELEASE_CHECKLIST.read_text(encoding="utf-8"),
    }

    for path, text in docs.items():
        assert "linkedin-apply-assistant" in text, path
        assert "0.1.3" in text, path

    assert "linkedin_apply_assistant" in docs["docs/install-and-configuration.md"]
    assert "python -m pip install ." in docs["docs/install-and-configuration.md"]
    assert 'python -m pip install -e ".[dev]"' in docs["docs/install-and-configuration.md"]
    assert (
        "python -m linkedin_apply_assistant.cli --help"
        in (docs["docs/install-and-configuration.md"])
    )


def test_public_source_and_pending_registry_wording_is_labeled() -> None:
    readme = README.read_text(encoding="utf-8").lower()
    install_doc = INSTALL_DOC.read_text(encoding="utf-8").lower()

    assert PUBLIC_REPO.lower() in readme
    assert f"git clone {PUBLIC_REPO.lower()}.git" in install_doc
    assert "<future-public-repository-url>" not in install_doc
    assert "does not claim a live public repository" not in readme
    assert "npm install -g linkedin-apply-assistant" in install_doc
    assert "powershell installer" in install_doc
    assert "install.ps1" in install_doc
    assert "pypi remains a future package channel" in install_doc
    assert "registry-publication-strategy.md" in README.read_text(encoding="utf-8")
    assert "registry-publication-strategy.md" in INSTALL_DOC.read_text(encoding="utf-8")


def test_changelog_tracks_v010_release_without_registry_publication_claims() -> None:
    changelog = CHANGELOG.read_text(encoding="utf-8")
    changelog_lower = changelog.lower()

    assert "## [Unreleased]" in changelog
    assert "## [0.1.3] - 2026-06-13" in changelog
    assert "## [0.1.2] - 2026-06-13" in changelog
    assert "## [0.1.1] - 2026-06-13" in changelog
    assert "## [0.1.0] - 2026-06-12" in changelog

    for forbidden in (
        "published to npm",
        "published to pypi",
        "published to testpypi",
    ):
        assert forbidden not in changelog_lower

    assert "registry publication strategy" in changelog_lower


def test_registry_strategy_keeps_current_version_source_only() -> None:
    text = REGISTRY_STRATEGY_DOC.read_text(encoding="utf-8").lower()

    assert "current package metadata version: `0.1.3`" in text
    assert "`v0.1.0` stays a github source-only release" in text
    assert "no registry should backfill `0.1.0`" in text
    assert "npm launcher release uses `0.1.1`" in text
    assert "docs-only npm package page refresh uses `0.1.2`" in text
    assert "powershell short-command readme refresh uses `0.1.3`" in text
    assert "`0.2.0`" in text


def test_package_metadata_points_to_public_repository() -> None:
    package = _package_json()
    pyproject_project = _pyproject()["project"]

    assert package["repository"] == {"type": "git", "url": NPM_REPOSITORY}
    assert package["homepage"] == HOMEPAGE
    assert package["bugs"] == {"url": ISSUES}
    assert pyproject_project["urls"] == {
        "Homepage": HOMEPAGE,
        "Repository": PUBLIC_REPO,
        "Issues": ISSUES,
    }


def test_package_includes_ci_policy_doc_but_excludes_workflow_internals() -> None:
    package_files = set(_package_json()["files"])

    assert "install.ps1" in package_files
    assert "pyproject.toml" in package_files
    assert "src/" in package_files
    assert "docs/ci-and-release-policy.md" in package_files
    assert "docs/registry-publication-strategy.md" in package_files
    assert ".github/dependabot.yml" not in package_files
    assert not any(path.startswith(".github/workflows/") for path in package_files)
