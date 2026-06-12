"""Safety policy, bounded audit metadata, and automation limits."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

from .contracts import SubmissionResult, SubmitDecision


POLICY_NAME = "phase16-disabled-submit-policy"
POLICY_VERSION = "2026-06-07"
DISABLED_SUBMISSION_REASON = "Browser submission is disabled in this package boundary."
FUTURE_SUBMIT_POLICY = (
    "Any future submit-capable release must require per-application interactive "
    "confirmation immediately before the specific application is sent. Broad approvals, "
    "background sending, and unattended modes are outside this package boundary."
)

SEARCH_LIMIT_DEFAULT = 10
SEARCH_LIMIT_CAP = 25
ASSIST_CYCLES_DEFAULT = 1
ASSIST_CYCLES_CAP = 25

BROWSER_PROFILE_WARNING = (
    "Browser profile warning: visible browser profiles can contain cookies, sessions, "
    "and local form data. Keep the profile directory local, ignored, and under your "
    "control."
)

RISK_STATUSES = frozenset({"login", "mfa", "checkpoint", "captcha", "rate_limited", "throttled"})


def utc_timestamp() -> str:
    """Return a stable UTC timestamp for audit records."""

    return datetime.now(timezone.utc).isoformat()


def domain_from_url(url: str | None) -> str:
    """Return a lower-case hostname without userinfo or port."""

    value = str(url or "").strip()
    parsed = urlparse(value)
    hostname = parsed.hostname
    if not hostname and "://" not in value and "/" not in value:
        hostname = value
    return (hostname or "").lower().rstrip(".")


def normalize_url_for_audit(url: str | None) -> str:
    """Return bounded URL metadata suitable for local reports."""

    parsed = urlparse(str(url or ""))
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""
    netloc = parsed.hostname.lower().rstrip(".")
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    path = (parsed.path or "").rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))


def clamp_search_limit(value: int | str | None) -> int:
    """Clamp public search requests to the package safety boundary."""

    return _clamp_non_negative_int(value, SEARCH_LIMIT_CAP)


def clamp_assist_cycles(value: int | str | None) -> int:
    """Clamp public assist cycles to the package safety boundary."""

    return _clamp_non_negative_int(value, ASSIST_CYCLES_CAP)


def _clamp_non_negative_int(value: int | str | None, cap: int) -> int:
    try:
        parsed = int(value) if value is not None else 0
    except (TypeError, ValueError):
        parsed = 0
    return min(max(parsed, 0), cap)


def backoff_delay(
    attempt: int,
    *,
    base_seconds: float = 1.0,
    cap_seconds: float = 30.0,
) -> float:
    """Return deterministic exponential backoff seconds without sleeping."""

    if attempt <= 0:
        return 0.0
    delay = base_seconds * (2 ** (attempt - 1))
    return min(float(delay), float(cap_seconds))


class DisabledSubmissionPolicy:
    """Submission policy that blocks every browser submission action."""

    policy = POLICY_NAME

    def decide(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> SubmissionResult:
        return SubmissionResult(
            status="disabled",
            reason=DISABLED_SUBMISSION_REASON,
            allowed=False,
        )

    def submit_decision(
        self,
        action: str,
        *,
        command: str = "apply",
        context: dict[str, Any] | None = None,
        confirmation_state: str = "",
    ) -> SubmitDecision:
        ctx = dict(context or {})
        url = normalize_url_for_audit(ctx.get("url") or ctx.get("apply_url") or "")
        domain = domain_from_url(url or ctx.get("domain") or "")
        return SubmitDecision(
            timestamp=utc_timestamp(),
            command=command,
            policy=f"{POLICY_NAME}@{POLICY_VERSION}",
            action=str(action or "submit"),
            allowed=False,
            status="disabled",
            reason=DISABLED_SUBMISSION_REASON,
            company=str(ctx.get("company") or ""),
            role=str(ctx.get("role") or ctx.get("title") or ""),
            url=url,
            domain=domain,
            ats=str(ctx.get("ats") or ""),
            confirmation_state=str(confirmation_state or "not_confirmed"),
        )

    def audit_event(
        self,
        action: str,
        *,
        command: str = "apply",
        context: dict[str, Any] | None = None,
        confirmation_state: str = "",
    ) -> dict[str, Any]:
        """Return a dictionary audit event for report writers."""

        return asdict(
            self.submit_decision(
                action,
                command=command,
                context=context,
                confirmation_state=confirmation_state,
            )
        )


def disabled_submit_audit_payload(
    *,
    command: str = "apply",
    action: str = "submit",
    context: dict[str, Any] | None = None,
    confirmation_state: str = "",
) -> dict[str, Any]:
    """Build a privacy-bounded disabled submit audit payload."""

    decision = DisabledSubmissionPolicy().audit_event(
        action,
        command=command,
        context=context,
        confirmation_state=confirmation_state,
    )
    return {
        "command": command,
        "timestamp": decision["timestamp"],
        "decision": decision,
        "events": [
            {
                "type": "submit_decision",
                "action": action,
                "status": decision["status"],
                "allowed": decision["allowed"],
                "policy": decision["policy"],
                "reason": decision["reason"],
                "company": decision["company"],
                "role": decision["role"],
                "url": decision["url"],
                "domain": decision["domain"],
                "ats": decision["ats"],
                "confirmation_state": decision["confirmation_state"],
                "timestamp": decision["timestamp"],
            }
        ],
        "summary": {
            "command": command,
            "policy": decision["policy"],
            "action": action,
            "status": decision["status"],
            "allowed": decision["allowed"],
            "submitted": 0,
            "reason": decision["reason"],
            "confirmation_state": decision["confirmation_state"],
        },
    }


__all__ = [
    "ASSIST_CYCLES_CAP",
    "ASSIST_CYCLES_DEFAULT",
    "BROWSER_PROFILE_WARNING",
    "DISABLED_SUBMISSION_REASON",
    "DisabledSubmissionPolicy",
    "FUTURE_SUBMIT_POLICY",
    "POLICY_NAME",
    "POLICY_VERSION",
    "RISK_STATUSES",
    "SEARCH_LIMIT_CAP",
    "SEARCH_LIMIT_DEFAULT",
    "backoff_delay",
    "clamp_assist_cycles",
    "clamp_search_limit",
    "disabled_submit_audit_payload",
    "domain_from_url",
    "normalize_url_for_audit",
]
