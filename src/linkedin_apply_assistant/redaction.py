"""Central report redaction for local JSON and Markdown artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from .form_engine import normalize_space
from .safety import normalize_url_for_audit


REDACTION_MARKER = "[REDACTED]"
MARKDOWN_VALUE_LIMIT = 180

_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "cookie",
    "credential",
    "auth",
    "session",
    "browser_profile",
    "browser-profile",
    "raw_html",
    "html",
    "screenshot",
    "resume_contents",
    "cover_letter_contents",
    "document_contents",
    "phone_answer",
    "email_answer",
    "answer_phone",
    "answer_email",
    "application_history",
    "candidate",
    "profile",
    "documents",
    "raw_form",
    "raw_state",
)

_SENSITIVE_EXACT_KEYS = {"answer", "email", "phone", "tel"}

_URL_KEYS = {"url", "apply_url", "search_url"}

_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsessionid\s*=", re.IGNORECASE),
    re.compile(r"\bcookie\s*[:=]", re.IGNORECASE),
    re.compile(r"<\s*html\b", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),
)


def _normalized_key(key: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(key or "").strip().lower())


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _is_url_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return normalized in _URL_KEYS or normalized.endswith("_url")


def _is_sensitive_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS)


def sanitize_report_payload(payload: Any) -> Any:
    """Return a sanitized copy of a report payload without mutating input."""

    return _sanitize_value(payload, key="")


def _sanitize_value(value: Any, *, key: Any) -> Any:
    if _is_sensitive_key(key):
        return REDACTION_MARKER
    if isinstance(value, Mapping):
        return {
            str(item_key): _sanitize_value(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, tuple):
        return [_sanitize_value(item, key=key) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value(item, key=key) for item in value]
    if isinstance(value, str):
        if _is_url_key(key):
            return normalize_url_for_audit(value)
        if _is_sensitive_value(value):
            return REDACTION_MARKER
        return value
    return value


def sanitize_markdown_value(value: Any) -> str:
    """Return compact Markdown-safe text for a sanitized report field."""

    sanitized = sanitize_report_payload(value)
    if isinstance(sanitized, (Mapping, list, tuple)):
        rendered = REDACTION_MARKER if sanitized == REDACTION_MARKER else str(sanitized)
    else:
        rendered = str(sanitized)
    rendered = normalize_space(rendered).replace("|", r"\|")
    if len(rendered) > MARKDOWN_VALUE_LIMIT:
        return f"{rendered[: MARKDOWN_VALUE_LIMIT - 3]}..."
    return rendered


__all__ = ["REDACTION_MARKER", "sanitize_markdown_value", "sanitize_report_payload"]
