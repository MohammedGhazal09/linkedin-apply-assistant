"""Fill-only ATS surfaces for the standalone assistant."""

from __future__ import annotations

from typing import Any

from .form_engine import FillResult, detect_ats, normalize_space
from .page_actions import (
    fill_first,
    fill_question,
    required_documents,
    set_file_first,
    visible_questions,
)
from .page_selectors import DOCUMENT_SELECTORS, PROFILE_FIELD_SELECTORS
from .qa_bank import QABank
from .safety import DISABLED_SUBMISSION_REASON, DisabledSubmissionPolicy


__all__ = ["DisabledSubmissionPolicy"]


SUPPORTED_ATS: tuple[str, ...] = (
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "smartrecruiters",
    "recruitee",
    "workable",
    "bamboohr",
    "icims",
    "taleo",
    "successfactors",
    "personio",
    "teamtailor",
    "jobvite",
    "resumator",
    "generic",
)


def normalize_ats(value: str | None, *, url: str | None = None) -> str:
    """Normalize an ATS name or infer it from a URL."""

    candidate = (value or "").strip().lower()
    if not candidate and url:
        candidate = detect_ats(url)
    if candidate in SUPPORTED_ATS:
        return candidate
    if candidate in {"unknown", ""}:
        return "generic"
    return candidate


def is_supported_ats(value: str | None) -> bool:
    """Return whether a normalized ATS surface is supported by package naming."""

    return normalize_ats(value) in SUPPORTED_ATS


def fill_external_apply_page(
    page: Any,
    ats: str,
    profile: dict[str, Any],
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
    documents: dict[str, Any] | None = None,
) -> FillResult:
    """Fill a selected external application page without submission."""

    normalized_ats = normalize_ats(ats)
    if page is None:
        return FillResult(
            required_empty=["A browser page object is required before filling can run."],
            reached_submit_step=False,
            surface=f"external:{normalized_ats}",
        )

    adapter_key = (
        normalized_ats if normalized_ats in {"greenhouse", "lever", "ashby"} else "generic"
    )
    return _fill_selected_external_adapter(
        page,
        adapter_key,
        profile,
        bank,
        qa_context or {},
        documents or {},
    )


def _profile_value(profile: dict[str, Any], key: str) -> Any:
    if key == "full_name":
        return profile.get("full_name") or " ".join(
            part
            for part in (
                normalize_space(profile.get("first_name")),
                normalize_space(profile.get("last_name")),
            )
            if part
        )
    return profile.get(key)


def _fill_profile_fields(page: Any, adapter_key: str, profile: dict[str, Any]) -> list[str]:
    filled: list[str] = []
    fields = PROFILE_FIELD_SELECTORS.get(adapter_key) or PROFILE_FIELD_SELECTORS["generic"]
    for key, selectors in fields.items():
        if fill_first(page, selectors, _profile_value(profile, key)):
            filled.append(key)
    return filled


def _document_value(documents: dict[str, Any], kind: str) -> Any:
    aliases = {
        "resume": ("resume", "cv", "resume_path"),
        "cover_letter": ("cover_letter", "cover", "cover_letter_path"),
    }
    for key in aliases[kind]:
        value = documents.get(key)
        if value:
            return value
    return None


def _fill_documents(page: Any, documents: dict[str, Any]) -> tuple[list[str], list[str]]:
    filled: list[str] = []
    required_empty: list[str] = []
    required = required_documents(page)
    for kind, selectors in DOCUMENT_SELECTORS.items():
        configured = _document_value(documents, kind)
        if configured:
            if set_file_first(page, selectors, configured):
                filled.append(kind)
            elif kind in required:
                required_empty.append(f"{kind} document path is missing or unreadable.")
        elif kind in required:
            required_empty.append(f"{kind} document path is required but not configured.")
    return filled, required_empty


def _fill_questions(
    page: Any,
    bank: QABank | None,
    qa_context: dict[str, Any],
) -> tuple[list[str], list[Any], list[Any]]:
    filled: list[str] = []
    required_empty: list[Any] = []
    unknown_questions: list[Any] = []

    for question in visible_questions(page):
        text = normalize_space(question.get("question") or question.get("label") or "")
        if not text:
            continue
        field_type = normalize_space(question.get("field_type") or "text")
        is_required = bool(question.get("required"))
        if bank is None:
            unknown_questions.append(
                {
                    "question": text,
                    "field_type": field_type,
                    "required": is_required,
                    "company": normalize_space(qa_context.get("company") or ""),
                    "role": normalize_space(
                        qa_context.get("role") or qa_context.get("title") or ""
                    ),
                    "ats": normalize_space(qa_context.get("ats") or ""),
                    "domain": normalize_space(qa_context.get("domain") or ""),
                }
            )
            if is_required:
                required_empty.append(text)
            continue
        answer = bank.find_answer(text, field_type=field_type, context=qa_context)
        if answer and fill_question(page, question, answer.get("answer", "")):
            filled.append(text)
            continue
        pending = bank.log_pending(
            text,
            context=qa_context,
            field_type=field_type,
            is_required=is_required,
        )
        unknown_questions.append(pending)
        if is_required:
            required_empty.append(text)
    return filled, required_empty, unknown_questions


def _fill_selected_external_adapter(
    page: Any,
    adapter_key: str,
    profile: dict[str, Any],
    bank: QABank | None,
    qa_context: dict[str, Any],
    documents: dict[str, Any],
) -> FillResult:
    filled = _fill_profile_fields(page, adapter_key, profile)
    document_filled, document_missing = _fill_documents(page, documents)
    question_filled, question_missing, unknown_questions = _fill_questions(page, bank, qa_context)
    filled.extend(f"document:{name}" for name in document_filled)
    filled.extend(f"question:{name}" for name in question_filled)
    reached_submit_step = bool(getattr(page, "at_submit_step", False))
    return FillResult(
        filled=filled,
        required_empty=[*document_missing, *question_missing],
        unknown_questions=unknown_questions,
        reached_submit_step=reached_submit_step,
        surface=f"external:{adapter_key}",
    )


def submit_disabled_status() -> tuple[bool, str]:
    """Return the disabled status for browser submission."""

    return False, DISABLED_SUBMISSION_REASON
