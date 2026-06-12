from __future__ import annotations

from pathlib import Path

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ISSUE_TEMPLATE_DIR = PACKAGE_ROOT / ".github" / "ISSUE_TEMPLATE"
ISSUE_FORMS = (
    "bug_report.yml",
    "feature_request.yml",
    "docs.yml",
    "safety_compliance.yml",
    "config_help.yml",
)
SENSITIVE_WARNING_TERMS = (
    "credentials",
    "cookies",
    "browser profiles",
    "screenshots",
    "CVs",
    "private documents",
    "generated local reports",
    "full private URLs",
    "live job history",
)


def _read(relative_path: str) -> str:
    return (PACKAGE_ROOT / relative_path).read_text(encoding="utf-8")


def _issue_form(name: str) -> dict[str, object]:
    payload = yaml.safe_load((ISSUE_TEMPLATE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict), name
    return payload


def test_root_community_docs_exist() -> None:
    for relative_path in ("SUPPORT.md", "GOVERNANCE.md", "CODE_OF_CONDUCT.md"):
        assert (PACKAGE_ROOT / relative_path).is_file(), relative_path


def test_issue_forms_and_config_exist() -> None:
    for name in ISSUE_FORMS:
        assert (ISSUE_TEMPLATE_DIR / name).is_file(), name

    config = yaml.safe_load((ISSUE_TEMPLATE_DIR / "config.yml").read_text(encoding="utf-8"))
    assert config["blank_issues_enabled"] is False
    assert config["contact_links"][0]["name"] == "Security vulnerability"


def test_issue_forms_parse_and_have_required_shape() -> None:
    for name in ISSUE_FORMS:
        form = _issue_form(name)
        assert form["name"]
        assert form["description"]
        assert form["title"]
        assert isinstance(form["body"], list)
        assert form["body"], name


def test_issue_forms_do_not_set_repository_metadata() -> None:
    forbidden = {"labels", "assignees", "projects", "milestone"}

    for name in ISSUE_FORMS:
        form = _issue_form(name)
        assert forbidden.isdisjoint(form), name


def test_issue_forms_collect_required_context() -> None:
    all_text = "\n".join(
        (ISSUE_TEMPLATE_DIR / name).read_text(encoding="utf-8") for name in ISSUE_FORMS
    ).lower()

    for phrase in (
        "sanitized command",
        "expected result",
        "actual result",
        "operating system",
        "python version",
        "package version or source commit",
        "minimal reproduction steps",
        "problem",
        "proposed behavior",
        "safety/privacy impact",
        "alternatives considered",
        "affected page or link",
        "suggested correction",
        "public safety/compliance concern summary",
        "expected safer behavior",
        "sanitized setup question",
        "redacted config shape or error text",
    ):
        assert phrase in all_text


def test_sensitive_warning_terms_appear_across_issue_forms() -> None:
    all_text = "\n".join(
        (ISSUE_TEMPLATE_DIR / name).read_text(encoding="utf-8") for name in ISSUE_FORMS
    )

    for term in SENSITIVE_WARNING_TERMS:
        assert term in all_text


def test_safety_form_routes_vulnerabilities_to_security_policy() -> None:
    text = _read(".github/ISSUE_TEMPLATE/safety_compliance.yml")

    assert "SECURITY.md" in text
    assert "exploit details" in text
    assert "private reporting" in text


def test_pull_request_template_contains_required_sections_and_prompts() -> None:
    text = _read(".github/PULL_REQUEST_TEMPLATE.md")
    lower_text = text.lower()

    for heading in (
        "# Summary",
        "# Rationale",
        "# Linked Issue",
        "# Safety And No-Submit Impact",
        "# Privacy-Sensitive File Check",
        "# Documentation Impact",
        "# Tests Or Commands Run",
        "# Release/Package Surface Impact",
        "# Residual Risk",
    ):
        assert heading in text

    for phrase in (
        "does this preserve no-submit behavior?",
        "does this avoid unattended/background sending?",
        "does this avoid private runtime data?",
        "are package manifest or npm files affected?",
        "are docs/tests updated?",
    ):
        assert phrase in lower_text


def test_support_conduct_and_contribution_routing_align() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            "SUPPORT.md",
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
        )
    )
    lower_text = combined.lower()

    for phrase in (
        "support.md",
        "security.md",
        "code_of_conduct.md",
        ".github/issue_template/",
        ".github/pull_request_template.md",
        "no-submit",
        "maintainer-private",
    ):
        assert phrase in lower_text

    for term in SENSITIVE_WARNING_TERMS:
        assert term in combined
