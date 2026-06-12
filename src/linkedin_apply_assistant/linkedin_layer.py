"""Pure LinkedIn URL and context helpers for the standalone assistant."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, unquote, urlparse, urlunparse

from .ats_handlers import fill_external_apply_page
from .browser_sessions import page_auth_status
from .form_engine import DetectionResult, FillResult, detect_ats, normalize_space
from .page_actions import (
    fill_first,
    fill_question,
    required_documents,
    set_file_first,
    visible_questions,
)
from .page_selectors import DOCUMENT_SELECTORS, EASY_APPLY_ACTIONS, PROFILE_FIELD_SELECTORS
from .qa_bank import QABank


DEFAULT_SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def _is_linkedin_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def sanitize_linkedin_search_url(search_url: str | None) -> str:
    """Return a stable LinkedIn jobs-search URL without selected-job state."""

    parsed = urlparse(search_url or DEFAULT_SEARCH_URL)
    if not _is_linkedin_host(parsed.hostname):
        return search_url or DEFAULT_SEARCH_URL
    query = parse_qs(parsed.query)
    query.pop("currentJobId", None)
    query.pop("start", None)
    clean_query = urlencode(query, doseq=True)
    path = parsed.path or "/jobs/search/"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", clean_query, ""))


def linkedin_search_url_for_job(search_url: str, job_id: str) -> str:
    """Add a selected job id to a LinkedIn search URL."""

    parsed = urlparse(sanitize_linkedin_search_url(search_url))
    query = parse_qs(parsed.query)
    query["currentJobId"] = [str(job_id)]
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query, doseq=True), "")
    )


def linkedin_job_id_from_job_record(job: dict[str, Any]) -> str:
    """Extract a LinkedIn job id from a normalized job record."""

    for key in ("job_id", "linkedin_job_id", "id"):
        value = str(job.get(key) or "").strip()
        if value:
            return value
    url = str(job.get("url") or job.get("linkedin_url") or "")
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]currentJobId=(\d+)", url)
    return match.group(1) if match else ""


def _decode_linkedin_apply_url(url: str) -> str:
    """Decode common LinkedIn redirect wrappers around external application URLs."""

    parsed = urlparse(url or "")
    if not _is_linkedin_host(parsed.hostname):
        return url
    query = parse_qs(parsed.query)
    for key in ("url", "dest", "destination", "redirect"):
        values = query.get(key)
        if values:
            return unquote(values[0])
    return url


def _looks_like_apply_url(url: str) -> bool:
    """Return whether a URL looks like an external application destination."""

    if not url:
        return False
    decoded = _decode_linkedin_apply_url(html.unescape(url))
    parsed = urlparse(decoded)
    if not parsed.scheme.startswith("http"):
        return False
    if _is_linkedin_host(parsed.hostname):
        return False
    haystack = f"{parsed.netloc} {parsed.path} {parsed.query}".lower()
    return detect_ats(decoded) != "unknown" or any(
        token in haystack for token in ("apply", "job", "career", "position", "opening")
    )


def _external_apply_url_candidate(
    url: str,
    *,
    require_apply_signal: bool = False,
) -> str:
    """Return a decoded external apply URL candidate, or an empty string."""

    decoded = _decode_linkedin_apply_url(html.unescape(url or ""))
    if require_apply_signal and not _looks_like_apply_url(decoded):
        return ""
    parsed = urlparse(decoded)
    if parsed.scheme.startswith("http") and not _is_linkedin_host(parsed.hostname):
        return decoded
    return ""


def _external_apply_url_from_html(markup: str) -> str:
    """Extract the first plausible external application URL from an HTML fragment."""

    for match in re.finditer(r"""href=["']([^"']+)["']""", markup or "", re.IGNORECASE):
        candidate = _external_apply_url_candidate(match.group(1), require_apply_signal=True)
        if candidate:
            return candidate
    return ""


def current_linkedin_job_info(page: Any, card: Any | None = None) -> dict[str, str]:
    """Best-effort job context placeholder for later browser integration."""

    if isinstance(card, dict):
        return {
            "title": normalize_space(card.get("title")),
            "company": normalize_space(card.get("company")),
            "url": normalize_space(card.get("url")),
            "job_id": linkedin_job_id_from_job_record(card),
        }
    return {"title": "", "company": "", "url": "", "job_id": ""}


def detect_current_apply_surface(
    context: Any,
    profile: dict[str, Any] | None = None,
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
) -> DetectionResult:
    """Detect a fillable surface without starting browser work."""

    pages = getattr(context, "pages", None) or []
    for page in reversed(list(pages)):
        url = str(getattr(page, "url", "") or "")
        page_context = dict(qa_context or {})
        page_context.setdefault("apply_url", url)
        for key in ("job_id", "company", "role", "title"):
            value = getattr(page, key, "")
            if value and key not in page_context:
                page_context[key] = value
        auth_status = page_auth_status(page)
        if auth_status != "ready":
            page_context["blocked_reason"] = (
                f"{auth_status} page requires user action in the visible browser"
            )
            page_context["ats"] = "linkedin"
            return DetectionResult(
                surface="browser_blocked",
                page=page,
                ats="linkedin",
                job_context=page_context,
            )
        if (
            bool(getattr(page, "easy_apply_open", False))
            or getattr(page, "surface", "") == "linkedin_easy_apply"
        ):
            return DetectionResult(
                surface="linkedin_easy_apply",
                page=page,
                ats="linkedin",
                job_context=page_context,
            )
        ats = detect_ats(url)
        if ats != "unknown":
            page_context["ats"] = ats
            return DetectionResult(
                surface="external_ats", page=page, ats=ats, job_context=page_context
            )
        if bool(getattr(page, "has_form", False)):
            page_context["ats"] = "generic"
            return DetectionResult(
                surface="external_ats", page=page, ats="generic", job_context=page_context
            )
    return DetectionResult(surface="none", job_context=qa_context or {})


class CurrentSurfaceDetector:
    """ApplySurfaceDetector using package-local visible-page detection."""

    def __init__(
        self,
        *,
        profile: dict[str, Any] | None = None,
        bank: QABank | None = None,
        qa_context: dict[str, Any] | None = None,
    ) -> None:
        self.profile = profile or {}
        self.bank = bank
        self.qa_context = qa_context or {}

    def detect(self, session: Any) -> DetectionResult:
        return detect_current_apply_surface(session, self.profile, self.bank, self.qa_context)


class CurrentSurfaceFillAdapter:
    """FillAdapter dispatching to package-local no-submit adapters."""

    def fill(
        self,
        detection: DetectionResult,
        profile: dict[str, Any],
        bank: QABank | None = None,
        qa_context: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
    ) -> FillResult:
        return fill_current_surface(detection, profile, bank, qa_context, documents)


def fill_current_surface(
    detection: DetectionResult,
    profile: dict[str, Any],
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
    documents: dict[str, Any] | None = None,
) -> FillResult:
    """Fill the detected surface when Phase 15 provides browser adapters."""

    if detection.surface == "external_ats":
        merged_context = dict(detection.job_context)
        merged_context.update(qa_context or {})
        return fill_external_apply_page(
            detection.page, detection.ats, profile, bank, merged_context, documents
        )
    if detection.surface == "linkedin_easy_apply":
        merged_context = dict(detection.job_context)
        merged_context.update(qa_context or {})
        return fill_linkedin_easy_apply(
            detection.page, profile, bank, merged_context, documents=documents
        )
    return FillResult(surface=detection.surface)


def _fill_easy_apply_profile(page: Any, profile: dict[str, Any]) -> list[str]:
    filled: list[str] = []
    for key, selectors in PROFILE_FIELD_SELECTORS["linkedin_easy_apply"].items():
        value = profile.get(key)
        if key == "full_name" and not value:
            value = " ".join(
                part
                for part in (
                    normalize_space(profile.get("first_name")),
                    normalize_space(profile.get("last_name")),
                )
                if part
            )
        if fill_first(page, selectors, value):
            filled.append(key)
    return filled


def _fill_easy_apply_documents(page: Any, documents: dict[str, Any]) -> tuple[list[str], list[str]]:
    filled: list[str] = []
    required_empty: list[str] = []
    required = required_documents(page)
    for kind, selectors in DOCUMENT_SELECTORS.items():
        value = documents.get(kind) or documents.get(f"{kind}_path")
        if value:
            if set_file_first(page, selectors, value):
                filled.append(kind)
            else:
                required_empty.append(f"{kind} document path is missing or unreadable.")
        elif kind in required:
            required_empty.append(f"{kind} document path is required but not configured.")
    return filled, required_empty


def _fill_easy_apply_questions(
    page: Any,
    bank: QABank | None,
    qa_context: dict[str, Any],
) -> tuple[list[str], list[Any], list[Any]]:
    filled: list[str] = []
    required_empty: list[Any] = []
    unknown_questions: list[Any] = []
    if bank is None:
        return filled, required_empty, unknown_questions
    for question in visible_questions(page):
        text = normalize_space(question.get("question") or question.get("label") or "")
        if not text:
            continue
        field_type = normalize_space(question.get("field_type") or "text")
        is_required = bool(question.get("required"))
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


def _next_easy_apply_action(page: Any) -> str:
    if hasattr(page, "next_easy_apply_action"):
        action = normalize_space(page.next_easy_apply_action()).lower()
        return "final" if "submit" in action else action
    return "final" if bool(getattr(page, "at_submit_step", False)) else ""


def _advance_easy_apply(page: Any, action: str) -> bool:
    if hasattr(page, "advance_easy_apply"):
        return bool(page.advance_easy_apply(action))
    return False


def fill_linkedin_easy_apply(
    page: Any,
    profile: dict[str, Any],
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
    easy_btn: Any | None = None,
    documents: dict[str, Any] | None = None,
) -> FillResult:
    """Fill LinkedIn Easy Apply without performing final submission."""

    context = qa_context or {}
    docs = documents or {}
    filled = _fill_easy_apply_profile(page, profile)
    document_filled, document_missing = _fill_easy_apply_documents(page, docs)
    question_filled, question_missing, unknown_questions = _fill_easy_apply_questions(
        page, bank, context
    )
    filled.extend(f"document:{name}" for name in document_filled)
    filled.extend(f"question:{name}" for name in question_filled)

    reached_submit_step = False
    for _ in range(5):
        action = _next_easy_apply_action(page)
        if not action:
            break
        if action in {item.lower() for item in EASY_APPLY_ACTIONS["final"]}:
            reached_submit_step = True
            break
        if action in {item.lower() for item in EASY_APPLY_ACTIONS["advance"]}:
            if not _advance_easy_apply(page, action):
                break
            filled.append(f"advanced:{action}")
            continue
        break

    if bool(getattr(page, "at_submit_step", False)):
        reached_submit_step = True
    return FillResult(
        filled=filled,
        required_empty=[*document_missing, *question_missing],
        unknown_questions=unknown_questions,
        reached_submit_step=reached_submit_step,
        surface="linkedin_easy_apply",
    )


class StaticLinkedInDiscovery:
    """LinkedInDiscovery implementation backed by preloaded records."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []

    def discover(self, request: Any) -> list[dict[str, Any]]:
        return list(self.records)


class BrowserLinkedInDiscovery:
    """Visible-browser LinkedIn discovery adapter."""

    def __init__(self, session_factory: Any | None = None) -> None:
        self.session_factory = session_factory

    def discover(self, request: Any) -> list[dict[str, Any]]:
        if self.session_factory is None:
            raise RuntimeError(
                "Live LinkedIn discovery requires a configured browser session factory."
            )
        session = self.session_factory.open(request)
        try:
            if request.search_url:
                session.open_url(request.search_url)
            page = (
                list(getattr(session, "pages", []) or [])[-1]
                if getattr(session, "pages", None)
                else None
            )
            if page is None:
                return []
            if hasattr(page, "linkedin_jobs"):
                return list(page.linkedin_jobs(limit=request.limit))
            return []
        finally:
            if getattr(session, "close_on_exit", False):
                session.close()


def run_linkedin_search_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Return a status for callers that have not supplied a discovery adapter."""

    return {"status": "not_configured", "reason": "Use the package search workflow with discovery."}


def run_linkedin_json_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Return a disabled status for JSON-driven browser orchestration."""

    return {"status": "disabled", "reason": "JSON browser orchestration is not enabled."}


def run_assistive_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Return a status for callers that have not supplied assist dependencies."""

    return {
        "status": "not_configured",
        "reason": "Use the package assist workflow with a session factory.",
    }
