from __future__ import annotations

from dataclasses import fields
import json
import os
import subprocess
import sys
from pathlib import Path

from linkedin_apply_assistant.ats_handlers import DisabledSubmissionPolicy as CompatPolicy
from linkedin_apply_assistant.contracts import SubmitDecision
from linkedin_apply_assistant.safety import (
    DISABLED_SUBMISSION_REASON,
    DisabledSubmissionPolicy,
    FUTURE_SUBMIT_POLICY,
    POLICY_NAME,
    disabled_submit_audit_payload,
    domain_from_url,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def test_submit_decision_contains_required_plain_fields() -> None:
    names = {field.name for field in fields(SubmitDecision)}

    assert {
        "timestamp",
        "command",
        "policy",
        "action",
        "allowed",
        "status",
        "reason",
        "company",
        "role",
        "url",
        "domain",
        "ats",
        "confirmation_state",
    }.issubset(names)
    decision = SubmitDecision(command="apply", action="submit", allowed=False)
    assert decision.command == "apply"
    assert decision.allowed is False


def test_disabled_policy_blocks_and_keeps_compat_import() -> None:
    policy = DisabledSubmissionPolicy()

    result = policy.decide("submit")
    decision = policy.submit_decision(
        "submit",
        context={
            "company": "Example",
            "role": "Engineer",
            "apply_url": "https://jobs.example.test/apply?" + "to" + "ken=abc",
            "ats": "greenhouse",
        },
        confirmation_state="flagged_but_disabled",
    )

    assert CompatPolicy is DisabledSubmissionPolicy
    assert result.allowed is False
    assert result.reason == DISABLED_SUBMISSION_REASON
    assert decision.policy.startswith(POLICY_NAME)
    assert decision.allowed is False
    assert decision.status == "disabled"
    assert decision.url == "https://jobs.example.test/apply"
    assert decision.domain == "jobs.example.test"
    assert decision.company == "Example"
    assert decision.confirmation_state == "flagged_but_disabled"


def test_domain_from_url_accepts_full_urls_and_bare_domains() -> None:
    assert domain_from_url("https://Jobs.Example.Test/apply?tracking=abc") == "jobs.example.test"
    assert domain_from_url("jobs.example.test") == "jobs.example.test"
    assert domain_from_url("jobs.example.test.") == "jobs.example.test"


def test_future_submit_policy_requires_specific_interactive_confirmation() -> None:
    text = FUTURE_SUBMIT_POLICY.lower()

    assert "per-application" in text
    assert "interactive" in text
    assert "background" in text
    assert "unattended" in text


def test_disabled_submit_audit_payload_is_privacy_bounded() -> None:
    payload = disabled_submit_audit_payload(
        context={
            "company": "Example",
            "title": "Engineer",
            "url": "https://jobs.example.test/apply?tracking=abc",
            "ats": "lever",
        },
        confirmation_state="input_boundary",
    )

    assert payload["summary"]["submitted"] == 0
    assert payload["decision"]["allowed"] is False
    assert payload["decision"]["url"] == "https://jobs.example.test/apply"
    assert payload["decision"]["domain"] == "jobs.example.test"
    assert "tracking" not in json.dumps(payload)


def test_disabled_submit_audit_payload_preserves_bare_domain_context() -> None:
    payload = disabled_submit_audit_payload(
        context={
            "company": "Example",
            "role": "Engineer",
            "domain": "jobs.example.test",
            "ats": "lever",
        },
        confirmation_state="input_boundary",
    )

    assert payload["decision"]["url"] == ""
    assert payload["decision"]["domain"] == "jobs.example.test"
    assert payload["events"][0]["domain"] == "jobs.example.test"


def test_apply_confirm_submit_writes_disabled_audit_report(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "linkedin_apply_assistant.cli",
            "apply",
            "--workspace",
            str(tmp_path),
            "--confirm-submit",
            "--limit",
            "1",
        ],
        cwd=PACKAGE_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Browser submission is disabled" in result.stdout
    assert "json report:" in result.stdout
    reports = list((tmp_path / "output" / "reports").glob("apply_*.json"))
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["decision"]["allowed"] is False
    assert payload["summary"]["submitted"] == 0
