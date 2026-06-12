from __future__ import annotations

from pathlib import Path
from typing import Any

from linkedin_apply_assistant.ats_handlers import fill_external_apply_page
from linkedin_apply_assistant.form_engine import DetectionResult
from linkedin_apply_assistant.linkedin_layer import (
    detect_current_apply_surface,
    fill_current_surface,
    fill_linkedin_easy_apply,
)


PROFILE = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "full_name": "Ada Lovelace",
    "email": "ada@example.test",
    "phone": "+15550000000",
    "linkedin": "https://www.linkedin.com/in/ada",
    "portfolio": "https://ada.example.test",
    "github": "https://github.com/ada",
    "current_company": "Analytical Engines",
}


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://boards.greenhouse.io/example/jobs/1",
        surface: str = "",
        has_form: bool = True,
        required_docs: set[str] | None = None,
        questions: list[dict[str, Any]] | None = None,
        actions: list[str] | None = None,
    ) -> None:
        self.url = url
        self.surface = surface
        self.has_form = has_form
        self.required_documents = required_docs or set()
        self._questions = questions or []
        self._actions = actions or []
        self.fields: list[tuple[tuple[str, ...], str]] = []
        self.files: list[tuple[tuple[str, ...], Path]] = []
        self.answers: list[tuple[str, str]] = []
        self.advanced: list[str] = []
        self.at_submit_step = False
        self.submit_calls = 0

    def fill_field(self, selectors: tuple[str, ...], value: str) -> bool:
        self.fields.append((selectors, value))
        return True

    def set_file(self, selectors: tuple[str, ...], path: Path) -> bool:
        self.files.append((selectors, path))
        return True

    def visible_questions(self) -> list[dict[str, Any]]:
        return list(self._questions)

    def fill_question(self, question: dict[str, Any], answer: str) -> bool:
        self.answers.append((str(question.get("question") or question.get("label") or ""), answer))
        return True

    def next_easy_apply_action(self) -> str:
        if not self._actions:
            return ""
        return self._actions.pop(0)

    def advance_easy_apply(self, action: str) -> bool:
        self.advanced.append(action)
        if not self._actions:
            self.at_submit_step = True
        return True

    def submit(self) -> None:
        self.submit_calls += 1


class FakeSession:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


class FakeBank:
    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = answers or {}
        self.pending: list[dict[str, Any]] = []

    def find_answer(
        self,
        question_text: str,
        field_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        answer = self.answers.get(question_text)
        if not answer:
            return None
        return {"answer": answer, "field_type": field_type or "text"}

    def log_pending(
        self,
        question_text: str,
        context: dict[str, Any] | None = None,
        field_type: str | None = None,
        is_required: bool = False,
    ) -> dict[str, Any]:
        entry = {
            "question": question_text,
            "field_type": field_type or "text",
            "required": is_required,
            "company": (context or {}).get("company", ""),
        }
        self.pending.append(entry)
        return entry


def test_external_selected_ats_adapters_fill_profile_fields(tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("placeholder", encoding="utf-8")

    for ats in ("greenhouse", "lever", "ashby", "generic"):
        page = FakePage(required_docs={"resume"})

        result = fill_external_apply_page(
            page,
            ats,
            PROFILE,
            documents={"resume": resume},
        )

        assert result.surface == f"external:{ats}"
        assert result.filled
        assert "document:resume" in result.filled
        assert not result.required_empty
        assert page.fields
        assert len(page.files) == 1
        assert page.submit_calls == 0


def test_external_missing_required_document_is_structured_blocker() -> None:
    page = FakePage(required_docs={"resume"})

    result = fill_external_apply_page(page, "greenhouse", PROFILE, documents={})

    assert result.required_empty == ["resume document path is required but not configured."]
    assert not page.files
    assert page.submit_calls == 0


def test_external_optional_configured_document_without_upload_control_does_not_block(
    tmp_path: Path,
) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("placeholder", encoding="utf-8")
    page = FakePage(required_docs=set())
    page.set_file = lambda selectors, path: False  # type: ignore[method-assign]

    result = fill_external_apply_page(page, "lever", PROFILE, documents={"resume": resume})

    assert result.required_empty == []
    assert "document:resume" not in result.filled
    assert not page.files


def test_external_required_configured_document_failed_upload_blocks(tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("placeholder", encoding="utf-8")
    page = FakePage(required_docs={"resume"})
    page.set_file = lambda selectors, path: False  # type: ignore[method-assign]

    result = fill_external_apply_page(page, "greenhouse", PROFILE, documents={"resume": resume})

    assert result.required_empty == ["resume document path is missing or unreadable."]
    assert "document:resume" not in result.filled


def test_external_unknown_required_question_is_logged() -> None:
    page = FakePage(
        questions=[
            {
                "question": "Do you require sponsorship?",
                "field_type": "select",
                "required": True,
            }
        ]
    )
    bank = FakeBank()

    result = fill_external_apply_page(
        page,
        "lever",
        PROFILE,
        bank=bank,
        qa_context={"company": "Example"},
    )

    assert result.required_empty == ["Do you require sponsorship?"]
    assert result.unknown_questions == bank.pending
    assert bank.pending[0]["required"] is True
    assert page.submit_calls == 0


def test_external_required_question_without_bank_blocks_and_records_unknown() -> None:
    page = FakePage(
        questions=[
            {
                "question": "Do you require sponsorship?",
                "field_type": "select",
                "required": True,
            }
        ]
    )

    result = fill_external_apply_page(
        page,
        "lever",
        PROFILE,
        bank=None,
        qa_context={"company": "Example", "ats": "lever"},
    )

    assert result.required_empty == ["Do you require sponsorship?"]
    assert result.unknown_questions[0]["question"] == "Do you require sponsorship?"
    assert result.unknown_questions[0]["field_type"] == "select"
    assert result.unknown_questions[0]["required"] is True
    assert result.unknown_questions[0]["company"] == "Example"
    assert page.answers == []
    assert page.submit_calls == 0


def test_external_known_question_is_filled() -> None:
    page = FakePage(
        questions=[
            {
                "question": "Do you require sponsorship?",
                "field_type": "select",
                "required": True,
            }
        ]
    )
    bank = FakeBank({"Do you require sponsorship?": "No"})

    result = fill_external_apply_page(page, "ashby", PROFILE, bank=bank)

    assert "question:Do you require sponsorship?" in result.filled
    assert not result.required_empty
    assert page.answers == [("Do you require sponsorship?", "No")]
    assert page.submit_calls == 0


def test_easy_apply_fills_advances_and_stops_at_final_boundary(tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("placeholder", encoding="utf-8")
    page = FakePage(
        surface="linkedin_easy_apply",
        required_docs={"resume"},
        questions=[{"question": "Are you authorized to work?", "required": True}],
        actions=["Next", "Continue", "final"],
    )
    bank = FakeBank({"Are you authorized to work?": "Yes"})

    result = fill_linkedin_easy_apply(
        page,
        PROFILE,
        bank=bank,
        qa_context={"company": "Example"},
        documents={"resume": resume},
    )

    assert result.surface == "linkedin_easy_apply"
    assert result.reached_submit_step is True
    assert "document:resume" in result.filled
    assert "question:Are you authorized to work?" in result.filled
    assert page.advanced == ["next", "continue"]
    assert page.submit_calls == 0


def test_surface_detection_prefers_newest_easy_apply_page_and_dispatches(tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("placeholder", encoding="utf-8")
    old_page = FakePage(url="https://jobs.lever.co/example/1")
    easy_page = FakePage(surface="linkedin_easy_apply", actions=["final"])
    session = FakeSession([old_page, easy_page])

    detection = detect_current_apply_surface(
        session, qa_context={"company": "Example", "role": "Engineer"}
    )
    result = fill_current_surface(
        detection,
        PROFILE,
        documents={"resume": resume},
    )

    assert isinstance(detection, DetectionResult)
    assert detection.surface == "linkedin_easy_apply"
    assert result.reached_submit_step is True
    assert easy_page.submit_calls == 0


def test_surface_detection_handles_unknown_form_bearing_external_page() -> None:
    page = FakePage(url="https://example.test/apply", has_form=True)
    session = FakeSession([page])

    detection = detect_current_apply_surface(session)

    assert detection.surface == "external_ats"
    assert detection.ats == "generic"
