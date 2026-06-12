"""Visible-browser session boundary for assist workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import urlparse

from .contracts import AssistRequest, SearchRequest
from .paths import RuntimePaths, ensure_runtime_dirs
from .safety import BROWSER_PROFILE_WARNING, RISK_STATUSES


AUTH_PATH_MARKERS = (
    "login",
    "checkpoint",
    "challenge",
    "captcha",
    "rate-limit",
    "ratelimit",
    "throttle",
)
PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND = "python -m playwright install chromium"


def _is_linkedin_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def page_auth_status(page: Any) -> str:
    """Return a warning status for pages that need user action."""

    explicit = str(getattr(page, "auth_status", "") or "").strip().lower()
    if explicit in RISK_STATUSES:
        return explicit
    parsed = urlparse(str(getattr(page, "url", "") or ""))
    path = parsed.path.lower()
    haystack = f"{path} {_page_text(page)}".lower()
    if "captcha" in haystack:
        return "captcha"
    if "rate limit" in haystack or "rate-limit" in haystack or "too many requests" in haystack:
        return "rate_limited"
    if "throttle" in haystack or "temporarily restricted" in haystack:
        return "throttled"
    if not _is_linkedin_host(parsed.hostname):
        return "ready"
    if any(marker in path for marker in AUTH_PATH_MARKERS):
        return "checkpoint" if "checkpoint" in path or "challenge" in path else "login"
    return "ready"


def _page_text(page: Any) -> str:
    parts: list[str] = []
    for attr_name in ("title", "text", "body_text", "content"):
        attr = getattr(page, attr_name, "")
        try:
            value = attr() if callable(attr) else attr
        except TypeError:
            value = ""
        if value:
            parts.append(str(value))
    return " ".join(parts)


def browser_profile_warning() -> str:
    """Return the reusable visible-browser profile warning."""

    return BROWSER_PROFILE_WARNING


@dataclass
class VisibleBrowserSession:
    """Thin wrapper around a visible browser context."""

    context: Any
    close_on_exit: bool = False

    @property
    def pages(self) -> Sequence[Any]:
        return list(getattr(self.context, "pages", []) or [])

    def open_url(self, url: str) -> None:
        pages = list(self.pages)
        page = pages[-1] if pages else self.context.new_page()
        page.goto(url)

    def close(self) -> None:
        manager = getattr(self, "_playwright_manager", None)
        try:
            self.context.close()
        finally:
            if manager is not None:
                manager.stop()

    def warnings(self) -> list[str]:
        warnings: list[str] = [browser_profile_warning()]
        for page in self.pages:
            status = page_auth_status(page)
            if status != "ready":
                warnings.append(f"{status} page requires user action in the visible browser")
        return warnings


class VisibleBrowserSessionFactory:
    """Factory for user-visible browser sessions backed by RuntimePaths."""

    def __init__(self, paths: RuntimePaths, *, close_on_exit: bool = False) -> None:
        self.paths = paths
        self.close_on_exit = close_on_exit

    def open(self, request: AssistRequest | SearchRequest) -> VisibleBrowserSession:
        ensure_runtime_dirs(self.paths, include_browser_profile=True)
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Browser setup failed: Playwright is required for live visible-browser workflows.\n"
                f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND}\n"
                f"Browser profile: {self.paths.browser_profile_dir}\n"
                "You can choose another profile with --browser-profile <path>."
            ) from exc

        manager = sync_playwright().start()
        try:
            context = manager.chromium.launch_persistent_context(
                str(self.paths.browser_profile_dir),
                headless=False,
            )
        except Exception as exc:
            manager.stop()
            raise RuntimeError(
                "Browser setup failed: Chromium could not be launched.\n"
                f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND}\n"
                f"Browser profile: {self.paths.browser_profile_dir}\n"
                "You can choose another profile with --browser-profile <path>."
            ) from exc
        session = VisibleBrowserSession(context=context, close_on_exit=self.close_on_exit)
        setattr(session, "_playwright_manager", manager)
        return session

    @staticmethod
    def auth_status(page: Any) -> str:
        return page_auth_status(page)


__all__ = [
    "VisibleBrowserSession",
    "VisibleBrowserSessionFactory",
    "browser_profile_warning",
    "page_auth_status",
    "PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND",
]
