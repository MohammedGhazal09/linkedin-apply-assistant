from __future__ import annotations

import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1] if PACKAGE_ROOT.parent.name == "standalone" else PACKAGE_ROOT
SRC_DIR = PACKAGE_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from linkedin_apply_assistant.apply_reports import (
    write_assistive_session_report,
    write_json_report,
    write_markdown_report,
)
from linkedin_apply_assistant.config import load_config
from linkedin_apply_assistant.form_engine import (
    append_applied_job_id,
    load_applied_job_ids,
)
from linkedin_apply_assistant.paths import ensure_runtime_dirs, resolve_runtime_paths
from linkedin_apply_assistant.qa_bank import QABank


REPORT_PREFIX = "phase14-isolation"


def _root_report_markers() -> set[Path]:
    markers: set[Path] = set()
    for base in (REPO_ROOT / "output", REPO_ROOT / "reports"):
        if base.exists():
            markers.update(path.relative_to(REPO_ROOT) for path in base.rglob(f"{REPORT_PREFIX}*"))
    return markers


def test_ensure_runtime_dirs_creates_only_explicit_runtime_directories(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)

    returned = ensure_runtime_dirs(paths)

    assert returned is paths
    for directory in (
        paths.config_dir,
        paths.data_dir,
        paths.cache_dir,
        paths.output_dir,
        paths.reports_dir,
    ):
        assert directory.is_dir()
    assert not paths.browser_profile_dir.exists()
    assert not paths.config_file.exists()
    assert not paths.qa_bank_file.exists()

    ensure_runtime_dirs(paths, include_browser_profile=True)
    assert paths.browser_profile_dir.is_dir()


def test_reports_write_under_selected_runtime_without_touching_repo_roots(
    tmp_path: Path,
) -> None:
    before = _root_report_markers()
    paths = ensure_runtime_dirs(resolve_runtime_paths(workspace=tmp_path))

    json_path = write_json_report(
        {"summary": {"total": 1}},
        paths=paths,
        filename_prefix=REPORT_PREFIX,
    )
    session_json, session_markdown = write_assistive_session_report(
        {"summary": {"filled": 1}, "events": []},
        {"name": "Example Candidate"},
        paths=paths,
    )

    assert json_path.parent == paths.reports_dir
    assert session_json.parent == paths.reports_dir
    assert session_markdown.parent == paths.reports_dir
    session_payload = json.loads(session_json.read_text(encoding="utf-8"))
    assert "candidate" not in session_payload
    assert "Example Candidate" not in session_markdown.read_text(encoding="utf-8")
    assert _root_report_markers() == before


def test_report_writers_do_not_overwrite_same_prefix(tmp_path: Path) -> None:
    first = write_json_report({"sequence": 1}, reports_dir=tmp_path, filename_prefix=REPORT_PREFIX)
    second = write_json_report({"sequence": 2}, reports_dir=tmp_path, filename_prefix=REPORT_PREFIX)

    assert first != second
    assert json.loads(first.read_text(encoding="utf-8"))["sequence"] == 1
    assert json.loads(second.read_text(encoding="utf-8"))["sequence"] == 2


def test_markdown_report_includes_nested_assist_and_search_job_context(tmp_path: Path) -> None:
    report_path = write_markdown_report(
        {
            "summary": {"events": 2},
            "events": [
                {"type": "filled", "job": {"company": "Example Co", "role": "Engineer"}},
                {"type": "job", "company": "Search Co", "title": "Python Developer"},
            ],
        },
        reports_dir=tmp_path,
        filename_prefix=REPORT_PREFIX,
    )

    content = report_path.read_text(encoding="utf-8")

    assert "Example Co Engineer" in content
    assert "Search Co Python Developer" in content


def test_qa_bank_uses_runtime_bank_and_pending_files(tmp_path: Path) -> None:
    paths = ensure_runtime_dirs(resolve_runtime_paths(workspace=tmp_path))
    paths.qa_bank_file.write_text(
        """
qa_pairs:
  - id: contact-email
    patterns:
      - email address
    answer: "{email}"
    field_type: email
""".lstrip(),
        encoding="utf-8",
    )

    bank = QABank.from_runtime_paths(paths, profile={"email": "candidate@example.com"})

    answer = bank.find_answer("What is your email address?", field_type="email")
    assert answer is not None
    assert answer["answer"] == "candidate@example.com"

    bank.log_pending(
        "Can you relocate?",
        context={
            "company": "Example Co",
            "role": "Engineer",
            "ats": "lever",
            "apply_url": "https://jobs.example.test/apply?private=abc",
        },
    )
    pending_name = "pending" + "_questions.md"
    pending_text = (paths.data_dir / pending_name).read_text(encoding="utf-8")
    assert "jobs.example.test" in pending_text
    assert "https://jobs.example.test/apply" not in pending_text


def test_qa_bank_rejects_incompatible_field_type_fallbacks(tmp_path: Path) -> None:
    bank_file = tmp_path / "qa.yml"
    bank_file.write_text(
        """
qa_pairs:
  - id: salary-text
    patterns:
      - expected salary
    answer: "$150k"
    field_type: text
  - id: sponsorship-choice
    patterns:
      - require sponsorship
    answer: "No"
    field_type: radio_or_select
""".lstrip(),
        encoding="utf-8",
    )
    bank = QABank(bank_file=bank_file)

    assert bank.find_answer("Expected salary", field_type="select") is None
    text_answer = bank.find_answer("Expected salary", field_type="text")
    radio_answer = bank.find_answer("Do you require sponsorship?", field_type="radio")
    assert text_answer is not None
    assert text_answer["answer"] == "$150k"
    assert radio_answer is not None
    assert radio_answer["answer"] == "No"
    assert bank.find_answer("Do you require sponsorship?", field_type="text") is None


def test_config_documents_are_optional_and_workspace_resolved(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
documents:
  resume: "documents/resume.example.pdf"
  cover_letter: "documents/cover-letter.example.pdf"
  portfolio: "https://example.com/portfolio"
""".lstrip(),
        encoding="utf-8",
    )

    empty_config = load_config()
    config = load_config(config_file, workspace=tmp_path)

    assert empty_config.documents == {}
    assert empty_config.document_paths == {}
    assert config.documents["resume"] == tmp_path / "documents" / "resume.example.pdf"
    assert config.documents["cover_letter"] == tmp_path / "documents" / "cover-letter.example.pdf"
    assert config.documents["portfolio"] == "https://example.com/portfolio"


def test_applied_job_helpers_use_explicit_jsonl_path(tmp_path: Path) -> None:
    applied_name = "applied" + "_job_ids.jsonl"
    applied_path = tmp_path / "state" / applied_name

    assert load_applied_job_ids(applied_path) == set()
    written_path = append_applied_job_id(
        applied_path,
        " job-123 ",
        metadata={"company": "Example Co"},
    )

    assert written_path == applied_path
    assert load_applied_job_ids(applied_path) == {"job-123"}


def test_applied_job_loader_expands_user_and_skips_non_object_jsonl(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    applied_name = "applied" + "_job_ids.jsonl"
    applied_path = Path("~") / "state" / applied_name

    written_path = append_applied_job_id(applied_path, "job-tilde")
    with written_path.open("a", encoding="utf-8") as handle:
        handle.write('["not", "an object"]\n')
        handle.write('"not an object either"\n')
        handle.write("{not json}\n")

    assert written_path == home / "state" / applied_name
    assert load_applied_job_ids(applied_path) == {"job-tilde"}
