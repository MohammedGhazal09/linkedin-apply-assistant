from __future__ import annotations

from typing import Any

from linkedin_apply_assistant.browser_sessions import (
    VisibleBrowserSession,
    browser_profile_warning,
    page_auth_status,
)
from linkedin_apply_assistant.safety import (
    ASSIST_CYCLES_CAP,
    BROWSER_PROFILE_WARNING,
    SEARCH_LIMIT_CAP,
    backoff_delay,
    clamp_assist_cycles,
    clamp_search_limit,
)


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://www.linkedin.com/jobs/search/",
        title: str = "",
        body_text: str = "",
        auth_status: str = "",
    ) -> None:
        self.url = url
        self._title = title
        self.body_text = body_text
        self.auth_status = auth_status

    def title(self) -> str:
        return self._title


class FakeContext:
    def __init__(self, pages: list[Any]) -> None:
        self.pages = pages

    def close(self) -> None:
        return None


def test_browser_profile_warning_is_exposed_from_session_layer() -> None:
    session = VisibleBrowserSession(context=FakeContext([]))

    assert browser_profile_warning() == BROWSER_PROFILE_WARNING
    assert session.warnings() == [BROWSER_PROFILE_WARNING]
    assert "cookies" in BROWSER_PROFILE_WARNING.lower()
    assert "sessions" in BROWSER_PROFILE_WARNING.lower()
    assert "form data" in BROWSER_PROFILE_WARNING.lower()


def test_page_auth_status_detects_explicit_platform_risk_statuses() -> None:
    for status in ("login", "mfa", "checkpoint", "captcha", "rate_limited", "throttled"):
        assert page_auth_status(FakePage(auth_status=status)) == status


def test_page_auth_status_detects_path_and_text_risk_signals() -> None:
    assert (
        page_auth_status(FakePage(url="https://www.linkedin.com/checkpoint/challenge"))
        == "checkpoint"
    )
    assert page_auth_status(FakePage(title="Security CAPTCHA check")) == "captcha"
    assert page_auth_status(FakePage(body_text="Too many requests. Please wait.")) == "rate_limited"
    assert page_auth_status(FakePage(body_text="Temporarily restricted by platform")) == "throttled"
    assert page_auth_status(FakePage(url="https://jobs.example.test/apply")) == "ready"


def test_visible_session_warnings_include_browser_profile_and_risk_status() -> None:
    session = VisibleBrowserSession(context=FakeContext([FakePage(auth_status="captcha")]))

    warnings = session.warnings()

    assert warnings[0] == BROWSER_PROFILE_WARNING
    assert any("captcha page requires user action" in warning for warning in warnings)


def test_automation_limits_are_conservative_and_deterministic() -> None:
    assert SEARCH_LIMIT_CAP == 25
    assert ASSIST_CYCLES_CAP == 25
    assert clamp_search_limit(100) == 25
    assert clamp_search_limit(-1) == 0
    assert clamp_assist_cycles(100) == 25
    assert clamp_assist_cycles(-1) == 0


def test_backoff_delay_is_exponential_capped_and_does_not_sleep() -> None:
    assert backoff_delay(0) == 0.0
    assert backoff_delay(-1) == 0.0
    assert backoff_delay(1, base_seconds=2.0, cap_seconds=30.0) == 2.0
    assert backoff_delay(4, base_seconds=2.0, cap_seconds=30.0) == 16.0
    assert backoff_delay(10, base_seconds=2.0, cap_seconds=30.0) == 30.0
