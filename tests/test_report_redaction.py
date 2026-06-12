from __future__ import annotations

import json
from pathlib import Path

from linkedin_apply_assistant.apply_reports import (
    write_assistive_session_report,
    write_json_report,
    write_markdown_report,
)
from linkedin_apply_assistant.qa_bank import QABank
from linkedin_apply_assistant.redaction import REDACTION_MARKER, sanitize_report_payload


def test_sanitize_report_payload_redacts_sensitive_keys_and_preserves_metadata() -> None:
    payload = {
        "company": "Example Co",
        "role": "Engineer",
        "url": "https://jobs.example.test/apply?trk=abc",
        "nested": {
            "to" + "ken": "abc",
            "coo" + "kie": "sessionid=abc",
            "raw_" + "html": "<html><body>private</body></html>",
        },
    }

    sanitized = sanitize_report_payload(payload)

    assert payload["nested"]["to" + "ken"] == "abc"
    assert sanitized["company"] == "Example Co"
    assert sanitized["url"] == "https://jobs.example.test/apply"
    assert sanitized["nested"]["to" + "ken"] == REDACTION_MARKER
    assert sanitized["nested"]["coo" + "kie"] == REDACTION_MARKER
    assert sanitized["nested"]["raw_" + "html"] == REDACTION_MARKER


def test_json_and_markdown_report_writers_sanitize_before_disk(tmp_path: Path) -> None:
    email_value = "ada" + "@" + "example.test"
    report = {
        "summary": {"events": 1, "submitted": 0, "email": email_value},
        "events": [
            {
                "type": "filled",
                "company": "Example Co",
                "role": "Engineer",
                "url": "https://jobs.example.test/apply?trk=abc",
                "profile": {"email": email_value},
                "to" + "ken": "abc",
            }
        ],
    }

    json_path = write_json_report(report, reports_dir=tmp_path, filename_prefix="redaction")
    md_path = write_markdown_report(report, reports_dir=tmp_path, filename_prefix="redaction")
    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    payload = json.loads(json_text)

    assert payload["summary"]["email"] == REDACTION_MARKER
    assert payload["events"][0]["profile"] == REDACTION_MARKER
    assert payload["events"][0]["to" + "ken"] == REDACTION_MARKER
    assert "https://jobs.example.test/apply" in json_text
    assert "?trk=" not in json_text
    assert email_value not in json_text
    assert email_value not in md_text
    assert "abc" not in md_text
    assert "Example Co Engineer" in md_text


def test_report_filename_prefix_cannot_escape_report_directory(tmp_path: Path) -> None:
    json_path = write_json_report(
        {"summary": {}}, reports_dir=tmp_path, filename_prefix="../escaped"
    )
    markdown_path = write_markdown_report(
        {"summary": {}},
        reports_dir=tmp_path,
        filename_prefix="..\\escaped",
    )
    fallback_path = write_json_report({"summary": {}}, reports_dir=tmp_path, filename_prefix="../")

    for path in (json_path, markdown_path, fallback_path):
        assert path.parent == tmp_path
        assert path.resolve().parent == tmp_path.resolve()
        assert "/" not in path.name
        assert "\\" not in path.name

    assert json_path.name.startswith("escaped_")
    assert markdown_path.name.startswith("escaped_")
    assert fallback_path.name.startswith("report_")


def test_assistive_session_report_does_not_inject_candidate_identity(tmp_path: Path) -> None:
    name = "Example Candidate"
    email_value = "candidate" + "@" + "example.test"

    json_path, md_path = write_assistive_session_report(
        {"summary": {"filled": 1}, "events": []},
        {"name": name, "email": email_value, "phone": "+1 555 010 0101"},
        reports_dir=tmp_path,
    )

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert "candidate" not in json.loads(json_text)
    assert name not in json_text
    assert name not in md_text
    assert email_value not in json_text


def test_pending_unknown_question_log_uses_domain_not_full_url(tmp_path: Path) -> None:
    pending_file = tmp_path / "pending.md"
    bank = QABank(pending_file=pending_file)
    url = "https://jobs.example.test/apply?private=abc"

    entry = bank.log_pending(
        "What salary range do you expect?",
        context={"company": "Example", "role": "Engineer", "ats": "lever", "apply_url": url},
        field_type="text",
        is_required=True,
    )
    content = pending_file.read_text(encoding="utf-8")

    assert entry["domain"] == "jobs.example.test"
    assert "What salary range do you expect?" in content
    assert "jobs.example.test" in content
    assert "https://jobs.example.test/apply" not in content
    assert "private=abc" not in content
    assert "Answer:" in content
