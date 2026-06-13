from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_DOC = PACKAGE_ROOT / "docs" / "registry-publication-strategy.md"
PUBLISHING_DOC = PACKAGE_ROOT / "docs" / "publishing.md"
README = PACKAGE_ROOT / "README.md"
INSTALL_DOC = PACKAGE_ROOT / "docs" / "install-and-configuration.md"
CI_POLICY_DOC = PACKAGE_ROOT / "docs" / "ci-and-release-policy.md"
RELEASE_CHECKLIST = PACKAGE_ROOT / "RELEASE_CHECKLIST.md"
PACKAGE_JSON = PACKAGE_ROOT / "package.json"
PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
MANIFEST = PACKAGE_ROOT / "release-manifest.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lower(path: Path) -> str:
    return _read(path).lower()


def test_strategy_doc_exists_with_expected_name() -> None:
    assert STRATEGY_DOC.is_file()
    assert not PUBLISHING_DOC.exists()
    assert "# Registry Publication Strategy" in _read(STRATEGY_DOC)
    assert "registry and installer policy" in _lower(STRATEGY_DOC)


def test_strategy_is_linked_from_public_docs_and_checklist() -> None:
    expected_links = {
        README: "docs/registry-publication-strategy.md",
        INSTALL_DOC: "registry-publication-strategy.md",
        CI_POLICY_DOC: "registry-publication-strategy.md",
        RELEASE_CHECKLIST: "docs/registry-publication-strategy.md",
    }

    for path, link in expected_links.items():
        assert link in _read(path), path.name


def test_channel_matrix_records_current_and_future_channel_decisions() -> None:
    text = _lower(STRATEGY_DOC)

    required_phrases = (
        "github releases",
        "current source-only channel",
        "pypi",
        "primary future python registry",
        "testpypi",
        "required preflight",
        "npm",
        "public thin-launcher channel",
        "delegates to the python cli",
        "powershell installer",
        "no-admin windows convenience path",
        "github packages",
        "deferred",
    )
    for phrase in required_phrases:
        assert phrase in text

    assert (
        "| channel | current status | future status | rationale | prerequisites | publish trigger | verification | rollback or remediation |"
        in text
    )


def test_v010_stays_source_only_and_future_versions_are_policy_examples() -> None:
    text = _lower(STRATEGY_DOC)
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.1.4"
    assert package["version"] == "0.1.4"
    assert "`v0.1.0` stays a github source-only release" in text
    assert "no registry should backfill `0.1.0`" in text
    assert "first registry release must use a later explicitly approved package version" in text
    assert "npm launcher release uses `0.1.1`" in text
    assert "docs-only npm package page refresh uses `0.1.2`" in text
    assert "powershell short-command readme refresh uses `0.1.3`" in text
    assert "cli no-command and `config` shorthand fix uses `0.1.4`" in text
    assert "`0.2.0`" in text
    assert "semver decisions" in text


def test_ownership_authentication_and_permission_boundaries_are_documented() -> None:
    text = _lower(STRATEGY_DOC)

    for phrase in (
        "maintainer-owned or maintainer-controlled",
        "account 2fa",
        "pypi trusted publishing",
        "github actions oidc",
        "npm trusted publishing",
        "no shared long-lived registry tokens",
        "protected github environments",
        "`testpypi`, `pypi`, and `npm`",
        "`release.yml`",
        "`id-token: write`",
        "`attestations: write`",
        "`packages: write`",
        "does not grant those permissions",
    ):
        assert phrase in text


def test_future_publish_gates_are_documented_without_running_live_checks() -> None:
    text = _lower(STRATEGY_DOC)
    checklist = _lower(RELEASE_CHECKLIST)
    combined = f"{text}\n{checklist}"

    for phrase in (
        "python -m build",
        "twine check dist/*",
        "local wheel install smoke",
        "npm pack --dry-run --json",
        "package contents inspection",
        "powershell installer parser check",
        "python scripts\\release.py manifest --check",
        "python scripts\\release.py verify",
        "gitleaks",
        "read-only npm, pypi, and testpypi registry",
        "live registry checks stay out of default pytest and ci",
    ):
        assert phrase in combined


def test_future_approval_templates_name_required_fields() -> None:
    text = _lower(STRATEGY_DOC)

    for section in (
        "testpypi preflight",
        "pypi release",
        "npm launcher release",
        "powershell installer update",
        "github release asset work",
    ):
        assert section in text

    for phrase in (
        "repository:",
        "version:",
        "channel:",
        "workflow or manual action:",
        "exact mutation:",
    ):
        assert phrase in text


def test_rollback_and_remediation_limits_are_documented() -> None:
    text = _lower(STRATEGY_DOC)

    for phrase in (
        "pypi: prefer yanking",
        "deletion is disruptive",
        "testpypi: cleanup is acceptable for preflight mistakes",
        "npm: unpublish is limited",
        "deprecation is often the safer remediation path",
        "a used package version cannot be reused",
        "github releases: removing a release asset does not remove source archives",
        "do not add executable rollback scripts",
    ):
        assert phrase in text


def test_current_install_surfaces_claim_npm_and_powershell_but_not_pypi() -> None:
    text = f"{_read(README)}\n{_read(INSTALL_DOC)}".lower()

    for forbidden in (
        "published on pypi",
        "published on testpypi",
        "npm publish",
        "pypi publish",
        "testpypi publish",
    ):
        assert forbidden not in text

    assert "npm install -g linkedin-apply-assistant" in text
    assert "powershell no-admin installer" in text
    assert "install.ps1" in text
    assert "pypi remains a future package channel" in text


def test_release_checklist_has_phase29_gate_without_scripted_publish_commands() -> None:
    checklist = _lower(RELEASE_CHECKLIST)
    assert "phase 29 registry publication strategy" in checklist
    assert "no shared long-lived registry tokens" in checklist
    assert "no executable registry rollback script" in checklist

    command_blocks = "\n".join(
        re.findall(r"```(?:powershell|text)?\n(.*?)```", checklist, flags=re.DOTALL)
    )
    for forbidden in ("npm publish", "twine upload"):
        assert forbidden not in command_blocks


def test_package_and_manifest_include_strategy_doc_and_policy_test() -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    package_files = set(package["files"])
    manifest_categories = {item["path"]: item["category"] for item in manifest["files"]}

    assert "docs/registry-publication-strategy.md" in package_files
    assert "install.ps1" in package_files
    assert "pyproject.toml" in package_files
    assert "src/linkedin_apply_assistant/*.py" in package_files
    assert manifest_categories["docs/registry-publication-strategy.md"] == "docs"
    assert manifest_categories["tests/test_registry_publication_strategy.py"] == "tests"
    assert manifest_categories["install.ps1"] == "installer"
