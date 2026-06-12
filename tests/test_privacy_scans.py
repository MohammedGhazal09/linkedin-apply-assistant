from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCAN_TARGETS = (
    PACKAGE_ROOT / "src" / "linkedin_apply_assistant",
    PACKAGE_ROOT / "README.md",
    PACKAGE_ROOT / "SAFETY.md",
    PACKAGE_ROOT / "LEGAL.md",
    PACKAGE_ROOT / "LICENSE",
    PACKAGE_ROOT / "THIRD_PARTY_NOTICES.md",
    PACKAGE_ROOT / "MIGRATION.md",
    PACKAGE_ROOT / "CONTRIBUTING.md",
    PACKAGE_ROOT / "SECURITY.md",
    PACKAGE_ROOT / "SUPPORT.md",
    PACKAGE_ROOT / "GOVERNANCE.md",
    PACKAGE_ROOT / "CODE_OF_CONDUCT.md",
    PACKAGE_ROOT / "CHANGELOG.md",
    PACKAGE_ROOT / "RELEASE_CHECKLIST.md",
    PACKAGE_ROOT / "release-manifest.json",
    PACKAGE_ROOT / "pyproject.toml",
    PACKAGE_ROOT / ".github",
    PACKAGE_ROOT / ".gitignore",
    PACKAGE_ROOT / "docs",
    PACKAGE_ROOT / "configs",
    PACKAGE_ROOT / "examples",
    PACKAGE_ROOT / "scripts",
    PACKAGE_ROOT / "tests",
)
TEXT_SUFFIXES = {"", ".py", ".md", ".yml", ".yaml", ".json", ".toml"}


def _join(*parts: str) -> str:
    return "".join(parts)


def _blocked_terms() -> dict[str, list[str]]:
    modules = (
        "form_engine",
        "qa_bank",
        "ats_handlers",
        "linkedin_layer",
        "apply_reports",
    )
    root_imports = [f"from {name}" for name in modules]
    root_imports.extend(f"import {name}" for name in modules)

    return {
        "root module imports": root_imports
        + [
            _join("scrapling", "_apply", "_pipeline"),
            _join("update", "-system", ".mjs"),
        ],
        "ecosystem runtime coupling": [
            _join("modes", "/"),
            _join("agent", "_prompts"),
            _join("dash", "board"),
            _join("bat", "ch"),
            _join("track", "er"),
            _join("portal", "_scanner"),
            _join("data", "/", "applications", ".md"),
            _join("config", "/", "profile", ".yml"),
        ],
        "credentials": [
            _join("python", "-", "dotenv"),
            _join("LINKEDIN", "_EMAIL"),
            _join("LINKEDIN", "_PASSWORD"),
            _join("linkedin", "-email"),
            _join("linkedin", "-password"),
            _join("password", ":"),
            _join("load", "_dotenv"),
        ],
        "browser profile paths": [
            _join("linkedin", "_user_data"),
            _join(".", "scrapling", "_browser_profile"),
        ],
        "private document defaults": [
            _join("cv", ".md"),
            _join("CV", ".pdf"),
            _join("output", "/", "cvs"),
        ],
        "report and state paths": [
            _join("REPORTS", "_DIR"),
            _join("output", "/", "auto-apply-reports"),
            _join("reports", "/", "0"),
            _join("data", "/", "application", "_qa_bank", ".yml"),
            _join("data", "/", "pending", "_questions", ".md"),
            _join("data", "/", "applied", "_job_ids", ".jsonl"),
        ],
        "known personal identifiers": [
            _join("Moh", "ammed"),
            _join("Ham", "zah"),
            _join("Gha", "zal"),
            _join("Santi", "ago"),
            _join("santi", "fer"),
        ],
        "unsafe apply enabling flags": [
            _join("enable", "_auto", "_submit"),
            _join("allow", "_un", "attended"),
            _join("global", "_submit", "_approved"),
            _join("background", "_submit", "_approved"),
        ],
        "package branding": [
            _join("Career", "-Ops"),
            _join("career", "-ops"),
            _join("Phase", " ", "13"),
        ],
        "certification claims": [
            _join("GDPR", " compliant"),
            _join("CCPA", " compliant"),
            _join("SOC", " 2 compliant"),
            _join("LinkedIn", " ToS compliant"),
            _join("certified", " compliant"),
        ],
    }


def _scan_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        if target.is_file():
            candidates = [target]
        elif target.exists():
            candidates = [path for path in target.rglob("*") if path.is_file()]
        else:
            candidates = []
        for path in candidates:
            if "__pycache__" in path.parts:
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _allowed_occurrence(path: Path, category: str) -> bool:
    rel = path.relative_to(PACKAGE_ROOT)
    neutral_attribution_files = {
        Path("THIRD_PARTY_NOTICES.md"),
        Path("MIGRATION.md"),
        Path("RELEASE_CHECKLIST.md"),
    }
    if rel == Path(".gitignore") and category in {"browser profile paths"}:
        return True
    release_allowlist_files = {
        Path("release-manifest.json"),
        Path("scripts/release.py"),
        Path("tests/test_release_manifest.py"),
    }
    if rel in release_allowlist_files and category in {
        "ecosystem runtime coupling",
        "credentials",
        "browser profile paths",
        "private document defaults",
        "report and state paths",
    }:
        return True
    if rel in neutral_attribution_files and category in {
        "ecosystem runtime coupling",
        "known personal identifiers",
        "package branding",
    }:
        return True
    return False


def _public_repo_normalized_text(text: str) -> str:
    """Keep the canonical public repo URL from tripping personal-name scans."""

    return text.replace(
        "MohammedGhazal09/linkedin-apply-assistant",
        "public-owner/linkedin-apply-assistant",
    ).replace(
        "MohammedGhazal09",
        "public-owner",
    )


def test_package_privacy_and_dependency_scan_is_clean() -> None:
    failures: list[str] = []

    for path in _scan_files():
        text = path.read_text(encoding="utf-8")
        scan_text = _public_repo_normalized_text(text)
        rel = path.relative_to(PACKAGE_ROOT)
        for category, terms in _blocked_terms().items():
            for term in terms:
                if term in scan_text:
                    if _allowed_occurrence(path, category):
                        continue
                    failures.append(f"{rel}: {category}: {term!r}")

    assert not failures, "\n".join(failures)


def test_scan_scope_covers_public_package_files() -> None:
    scanned = {path.relative_to(PACKAGE_ROOT) for path in _scan_files()}

    assert Path("README.md") in scanned
    assert Path("SAFETY.md") in scanned
    assert Path("LEGAL.md") in scanned
    assert Path("THIRD_PARTY_NOTICES.md") in scanned
    assert Path("MIGRATION.md") in scanned
    assert Path("CONTRIBUTING.md") in scanned
    assert Path("SECURITY.md") in scanned
    assert Path("SUPPORT.md") in scanned
    assert Path("GOVERNANCE.md") in scanned
    assert Path("CODE_OF_CONDUCT.md") in scanned
    assert Path(".github/ISSUE_TEMPLATE/bug_report.yml") in scanned
    assert Path(".github/ISSUE_TEMPLATE/feature_request.yml") in scanned
    assert Path(".github/ISSUE_TEMPLATE/docs.yml") in scanned
    assert Path(".github/ISSUE_TEMPLATE/safety_compliance.yml") in scanned
    assert Path(".github/ISSUE_TEMPLATE/config_help.yml") in scanned
    assert Path(".github/ISSUE_TEMPLATE/config.yml") in scanned
    assert Path(".github/PULL_REQUEST_TEMPLATE.md") in scanned
    assert Path("CHANGELOG.md") in scanned
    assert Path("RELEASE_CHECKLIST.md") in scanned
    assert Path("release-manifest.json") in scanned
    assert Path("pyproject.toml") in scanned
    assert Path(".gitignore") in scanned
    assert Path("scripts/quality.py") in scanned
    assert Path("scripts/release.py") in scanned
    assert Path("docs/install-and-configuration.md") in scanned
    assert Path("docs/apply.md") in scanned
    assert Path("configs/config.example.yml") in scanned
    assert Path("configs/qa_bank.example.yml") in scanned
    assert Path("examples/dry_run_input.example.json") in scanned
    assert Path("examples/reports/search-report.example.json") in scanned
    assert Path("examples/reports/apply-audit.example.json") in scanned
    assert Path("tests/test_privacy_scans.py") in scanned
    assert any(path.parts[:2] == ("src", "linkedin_apply_assistant") for path in scanned)


def test_safety_docs_cover_required_boundaries() -> None:
    docs = "\n".join(
        [
            (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8"),
            (PACKAGE_ROOT / "SAFETY.md").read_text(encoding="utf-8"),
            (PACKAGE_ROOT / "LEGAL.md").read_text(encoding="utf-8"),
            (PACKAGE_ROOT / "docs" / "apply.md").read_text(encoding="utf-8"),
        ]
    ).lower()

    for phrase in (
        "no-submit",
        "per-application",
        "mass applications",
        "unattended apply",
        "captcha",
        "mfa",
        "fake answers",
        "platform throttling",
        "browser profile",
        "not legal advice",
        "not a compliance certification",
    ):
        assert phrase in docs


def test_attribution_wording_stays_neutral() -> None:
    third_party = (PACKAGE_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    migration = (PACKAGE_ROOT / "MIGRATION.md").read_text(encoding="utf-8")
    readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    upstream_name = _join("Career", "-Ops")

    assert "LinkedIn-apply-assistant is the standalone package identity" in third_party
    assert "Product identity belongs to LinkedIn-apply-assistant" in migration
    assert upstream_name not in readme
    assert "stealth, bypass, anti-detection, or product identity claim" in migration


def test_gitignore_protects_private_runtime_paths() -> None:
    text = (PACKAGE_ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = (
        ".env",
        "configs/config.yml",
        "configs/qa_bank.yml",
        "data/",
        "output/",
        "reports/",
        "browser-profile/",
        "documents/",
        ".venv/",
        "build/",
        "dist/",
        "*.egg-info/",
    )

    for pattern in required_patterns:
        assert pattern in text


def test_redaction_policy_covers_sensitive_report_fields() -> None:
    from linkedin_apply_assistant.redaction import REDACTION_MARKER, sanitize_report_payload

    payload = {
        "pass" + "word": "x",
        "to" + "ken": "x",
        "coo" + "kie": "x",
        "browser" + "_profile": "x",
        "raw" + "_html": "<html>",
        "screen" + "shot": "x",
        "resume" + "_contents": "x",
        "cover" + "_letter" + "_contents": "x",
        "phone" + "_answer": "+1 555 010 0101",
        "email" + "_answer": "candidate" + "@" + "example.test",
        "application" + "_history": ["x"],
        "company": "Example",
    }

    sanitized = sanitize_report_payload(payload)

    assert sanitized["company"] == "Example"
    for key, value in sanitized.items():
        if key != "company":
            assert value == REDACTION_MARKER
