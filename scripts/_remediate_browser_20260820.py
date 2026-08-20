from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES: dict[str, str] = {
    "src/linkedin_apply_assistant/contracts.py": r'''"""Stable workflow contracts for the local no-submit assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .form_engine import DetectionResult, FillResult


@dataclass(frozen=True)
class JobRecord:
    job_id: str = ""
    title: str = ""
    company: str = ""
    url: str = ""
    location: str = ""
    source: str = "linkedin"
    search_url: str = ""
    ats: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchRequest:
    limit: int = 10
    search_url: str | None = None
    query: str | None = None
    location: str | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    approved_origins: tuple[str, ...] = ()
    paths: Any = None


@dataclass(frozen=True)
class SurfaceIdentity:
    url: str = ""
    title: str = ""
    surface: str = ""
    ats: str = ""
    job_id: str = ""

    def key(self) -> str:
        return "|".join((self.url, self.title, self.surface, self.ats, self.job_id))


@dataclass(frozen=True)
class ReportArtifact:
    kind: str
    path: Path


@dataclass
class SearchResult:
    command: str = "search"
    timestamp: str = ""
    search_url: str = ""
    jobs: list[JobRecord] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    reports: list[ReportArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class AssistEvent:
    type: str
    surface: str = ""
    ats: str = ""
    status: str = ""
    filled_count: int = 0
    required_empty_count: int = 0
    unknown_count: int = 0
    reached_submit_step: bool = False
    blocked_reason: str = ""
    job: dict[str, Any] = field(default_factory=dict)
    identity: SurfaceIdentity | None = None
    required_empty: list[Any] = field(default_factory=list)
    unknown_questions: list[Any] = field(default_factory=list)
    timestamp: str = ""


@dataclass(frozen=True)
class AssistRequest:
    start_url: str | None = None
    mode: str = "auto-watch"
    max_cycles: int = 1
    max_steps: int = 5
    poll_seconds: float = 0.25
    profile: dict[str, Any] = field(default_factory=dict)
    qa_context: dict[str, Any] = field(default_factory=dict)
    documents: dict[str, Any] = field(default_factory=dict)
    approved_origins: tuple[str, ...] = ()
    paths: Any = None


@dataclass
class AssistResult:
    command: str = "assist"
    timestamp: str = ""
    events: list[AssistEvent] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    reports: list[ReportArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResult:
    status: str = "disabled"
    reason: str = "Browser submission is disabled in this package boundary."
    allowed: bool = False


@dataclass(frozen=True)
class SubmitDecision:
    timestamp: str = ""
    command: str = ""
    policy: str = ""
    action: str = ""
    allowed: bool = False
    status: str = "disabled"
    reason: str = ""
    company: str = ""
    role: str = ""
    url: str = ""
    domain: str = ""
    ats: str = ""
    confirmation_state: str = ""


class BrowserSession(Protocol):
    close_on_exit: bool

    @property
    def pages(self) -> Sequence[Any]: ...
    def open_url(self, url: str) -> None: ...
    def close(self) -> None: ...


class BrowserSessionFactory(Protocol):
    def open(self, request: AssistRequest | SearchRequest) -> BrowserSession: ...


class LinkedInDiscovery(Protocol):
    def discover(self, request: SearchRequest) -> Sequence[JobRecord | Mapping[str, Any]]: ...


class ApplySurfaceDetector(Protocol):
    def detect(self, session: BrowserSession) -> DetectionResult: ...


class FillAdapter(Protocol):
    def fill(
        self,
        detection: DetectionResult,
        profile: dict[str, Any],
        bank: Any = None,
        qa_context: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
    ) -> FillResult: ...


class QAMatcher(Protocol):
    def find_answer(
        self,
        question_text: str,
        field_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...

    def log_pending(
        self,
        question_text: str,
        context: dict[str, Any] | None = None,
        field_type: str | None = None,
        is_required: bool = False,
    ) -> dict[str, Any]: ...


class SubmissionPolicy(Protocol):
    def decide(self, action: str, context: dict[str, Any] | None = None) -> SubmissionResult: ...


class ReportSink(Protocol):
    def write(self, command: str, report: dict[str, Any]) -> Sequence[ReportArtifact]: ...


__all__ = [
    "ApplySurfaceDetector", "AssistEvent", "AssistRequest", "AssistResult", "BrowserSession",
    "BrowserSessionFactory", "FillAdapter", "JobRecord", "LinkedInDiscovery", "QAMatcher",
    "ReportArtifact", "ReportSink", "SearchRequest", "SearchResult", "SubmissionPolicy",
    "SubmissionResult", "SubmitDecision", "SurfaceIdentity",
]
''',
    "src/linkedin_apply_assistant/form_engine.py": r'''"""Import-safe form and job-record primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .origin_policy import classify_ats_url
from .storage import atomic_private_write, process_local_lock


_real_print = print


def safe_print(*args: object, **kwargs: object) -> None:
    try:
        _real_print(*args, **kwargs)
    except UnicodeEncodeError:
        cleaned = [str(arg).encode("ascii", errors="replace").decode("ascii") for arg in args]
        _real_print(*cleaned, **kwargs)


@dataclass
class FillResult:
    filled: list[Any] = field(default_factory=list)
    required_empty: list[Any] = field(default_factory=list)
    unknown_questions: list[Any] = field(default_factory=list)
    reached_submit_step: bool = False
    surface: str = ""


@dataclass
class DetectionResult:
    surface: str = "none"
    page: Any = None
    ats: str = ""
    job_context: dict[str, Any] = field(default_factory=dict)


ATS_PATTERNS: dict[str, tuple[str, ...]] = {}


def detect_ats(url: str) -> str:
    return classify_ats_url(url)


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_jobs(input_file: Path) -> list[dict[str, Any]]:
    from .schemas import load_json_limited, normalize_job_record

    payload = load_json_limited(input_file)
    jobs = payload if isinstance(payload, list) else payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("job input must be a list or an object with a jobs list")
    return [normalize_job_record(job) for job in jobs]


def load_applied_job_ids(path: Path) -> set[str]:
    target = Path(path).expanduser()
    if not target.exists():
        return set()
    ids: set[str] = set()
    if target.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("applied job id file exceeds 5 MiB")
    for line in target.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and normalize_space(payload.get("job_id")):
            ids.add(normalize_space(payload["job_id"]))
    return ids


def append_applied_job_id(
    path: Path,
    job_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    clean = normalize_space(job_id)
    if not clean:
        raise ValueError("job_id is required")
    target = Path(path).expanduser()
    with process_local_lock(target):
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        payload = {"job_id": clean, "timestamp": datetime.now(timezone.utc).isoformat()}
        if metadata:
            payload["metadata"] = {
                key: normalize_space(value)[:500]
                for key, value in metadata.items()
                if key in {"company", "role", "ats", "domain"}
            }
        return atomic_private_write(
            target,
            existing + json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        )


__all__ = [
    "ATS_PATTERNS", "DetectionResult", "FillResult", "append_applied_job_id", "detect_ats",
    "load_applied_job_ids", "load_jobs", "normalize_space", "safe_print",
]
''',
    "src/linkedin_apply_assistant/browser_adapter.py": r'''"""Real Playwright DOM adapter shared by production and browser fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit
from uuid import uuid4

from .origin_policy import OriginPolicyError, require_application_url


ADVANCE_LABELS = frozenset({"next", "continue", "review", "review application"})
FINAL_TOKENS = ("submit", "send application", "apply now", "finish application")
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Control:
    control_id: str
    tag: str
    field_type: str
    name: str
    label: str
    required: bool
    disabled: bool
    visible: bool
    value_present: bool
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Action:
    kind: str = "none"
    label: str = ""


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _profile_key(control: Control) -> str:
    haystack = f"{control.label} {control.name}".lower()
    patterns = (
        ("email", ("email",)),
        ("phone", ("phone", "mobile", "telephone")),
        ("first_name", ("first name", "firstname", "given name")),
        ("last_name", ("last name", "lastname", "surname", "family name")),
        ("full_name", ("full name", "your name", "name")),
        ("linkedin", ("linkedin",)),
        ("github", ("github",)),
        ("portfolio", ("portfolio", "website", "personal site")),
        ("current_company", ("current company", "organization", "employer")),
        ("location", ("location", "city", "address")),
    )
    for key, tokens in patterns:
        if any(token in haystack for token in tokens):
            return key
    return ""


def _document_kind(control: Control) -> str:
    haystack = f"{control.label} {control.name}".lower()
    if "resume" in haystack or re.search(r"\bcv\b", haystack):
        return "resume"
    if "cover" in haystack:
        return "cover_letter"
    return ""


def _validate_document(path: str | Path) -> Path:
    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file():
        raise ValueError(f"Document path is not a regular file: {target}")
    if target.suffix.lower() not in {".pdf", ".doc", ".docx", ".txt"}:
        raise ValueError(f"Unsupported document type: {target.suffix}")
    if target.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("Document exceeds 10 MiB")
    return target


class PlaywrightPageAdapter:
    """Origin-checked operations over a real Playwright sync Page."""

    def __init__(
        self,
        page: Any,
        *,
        expected_ats: str | None = None,
        approved_origins: Iterable[str] | None = None,
    ) -> None:
        self.page = page
        self.expected_ats = expected_ats
        self.approved_origins = tuple(approved_origins or ())

    @property
    def url(self) -> str:
        return str(getattr(self.page, "url", "") or "")

    def assert_trusted(self) -> None:
        require_application_url(
            self.url,
            expected_ats=self.expected_ats,
            approved_origins=self.approved_origins,
        )

    def _root(self) -> Any:
        dialogs = self.page.locator('[role="dialog"]:visible')
        try:
            if dialogs.count() > 0:
                return dialogs.last
        except Exception:
            pass
        return self.page.locator("body")

    def _assign_control_ids(self) -> None:
        prefix = f"laa-{uuid4().hex[:10]}"
        self._root().locator("input, select, textarea").evaluate_all(
            """(elements, prefix) => elements.forEach((el, index) => {
                if (!el.dataset.laaControlId) el.dataset.laaControlId = `${prefix}-${index}`;
            })""",
            prefix,
        )

    def controls(self) -> list[Control]:
        self.assert_trusted()
        self._assign_control_ids()
        raw = self._root().locator("input, select, textarea").evaluate_all(
            """elements => elements.map(el => {
                const style = window.getComputedStyle(el);
                const label = (el.labels && el.labels[0] && el.labels[0].innerText) ||
                    el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
                    (el.closest('label') && el.closest('label').innerText) || el.name || el.id || '';
                const type = (el.getAttribute('type') || el.tagName || 'text').toLowerCase();
                const visible = type === 'file' || !(style.display === 'none' || style.visibility === 'hidden');
                const options = el.tagName === 'SELECT' ? Array.from(el.options).map(o => o.textContent || o.value) : [];
                const valuePresent = type === 'checkbox' || type === 'radio' ? !!el.checked : !!String(el.value || '').trim();
                return {
                    control_id: el.dataset.laaControlId || '', tag: el.tagName.toLowerCase(),
                    field_type: type, name: el.name || el.id || '', label: String(label || '').trim(),
                    required: !!el.required || el.getAttribute('aria-required') === 'true',
                    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
                    visible, value_present: valuePresent, options
                };
            })"""
        )
        return [
            Control(
                control_id=str(item.get("control_id") or ""),
                tag=str(item.get("tag") or ""),
                field_type=str(item.get("field_type") or "text"),
                name=_text(item.get("name")),
                label=_text(item.get("label"))[:1000],
                required=bool(item.get("required")),
                disabled=bool(item.get("disabled")),
                visible=bool(item.get("visible")),
                value_present=bool(item.get("value_present")),
                options=tuple(_text(option) for option in item.get("options") or []),
            )
            for item in raw
            if item.get("control_id")
        ]

    def _locator(self, control: Control) -> Any:
        return self._root().locator(f'[data-laa-control-id="{control.control_id}"]')

    def fill_control(self, control: Control, answer: Any, *, overwrite: bool = False) -> bool:
        self.assert_trusted()
        if control.disabled or not control.visible or answer is None:
            return False
        locator = self._locator(control)
        if control.value_present and not overwrite:
            return True
        value = str(answer).strip()
        if not value and control.field_type not in {"checkbox", "radio"}:
            return False
        try:
            if control.tag == "select":
                try:
                    locator.select_option(label=value, timeout=3000)
                except Exception:
                    locator.select_option(value=value, timeout=3000)
            elif control.field_type == "checkbox":
                yes = value.lower() in {"1", "true", "yes", "y", "on", "checked"}
                locator.check(timeout=3000) if yes else locator.uncheck(timeout=3000)
            elif control.field_type == "radio":
                if value.lower() in {
                    control.label.lower(), control.name.lower(), "1", "true", "yes", "y", "on"
                }:
                    locator.check(timeout=3000)
                else:
                    return False
            elif control.field_type == "file":
                return False
            else:
                locator.fill(value, timeout=3000)
            return True
        except Exception as exc:
            raise RuntimeError(f"Failed to fill reviewed control {control.label!r}") from exc

    def set_file(self, control: Control, path: str | Path) -> bool:
        self.assert_trusted()
        target = _validate_document(path)
        if control.field_type != "file" or control.disabled:
            return False
        try:
            self._locator(control).set_input_files(str(target), timeout=5000)
            return True
        except Exception as exc:
            raise RuntimeError(f"Failed to attach {target.name}") from exc

    def fill_surface(
        self,
        profile: dict[str, Any],
        bank: Any = None,
        context: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(context or {})
        documents = dict(documents or {})
        filled: list[str] = []
        required_empty: list[str] = []
        unknown: list[Any] = []
        for control in self.controls():
            if control.disabled or control.field_type in {"hidden", "submit", "button", "reset", "image"}:
                continue
            if control.field_type == "file":
                kind = _document_kind(control)
                configured = documents.get(kind) or documents.get(f"{kind}_path") if kind else None
                if configured:
                    if self.set_file(control, configured):
                        filled.append(f"document:{kind}")
                elif control.required:
                    required_empty.append(f"{kind or control.label or 'document'} is required")
                continue
            profile_key = _profile_key(control)
            answer = profile.get(profile_key) if profile_key else None
            if profile_key == "full_name" and not answer:
                answer = " ".join(
                    part for part in (_text(profile.get("first_name")), _text(profile.get("last_name"))) if part
                )
            if answer in (None, "") and bank is not None:
                record = bank.find_answer(control.label, field_type=control.field_type, context=context)
                answer = record.get("answer") if record else None
            if answer not in (None, ""):
                if self.fill_control(control, answer):
                    filled.append(profile_key or f"question:{control.label}")
                continue
            if control.value_present:
                filled.append(f"preserved:{profile_key or control.label}")
                continue
            if control.required:
                pending = (
                    bank.log_pending(
                        control.label,
                        context=context,
                        field_type=control.field_type,
                        is_required=True,
                    )
                    if bank is not None
                    else {
                        "question": control.label,
                        "field_type": control.field_type,
                        "required": True,
                        "ats": context.get("ats", ""),
                        "company": context.get("company", ""),
                        "role": context.get("role", context.get("title", "")),
                        "domain": context.get("domain", ""),
                    }
                )
                unknown.append(pending)
                required_empty.append(control.label or control.name or "required field")
        return {"filled": filled, "required_empty": required_empty, "unknown_questions": unknown}

    def next_action(self) -> Action:
        self.assert_trusted()
        actions = self._root().locator('button, input[type="button"], input[type="submit"]').evaluate_all(
            """elements => elements.map(el => ({
                text: String(el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim(),
                type: String(el.getAttribute('type') || '').toLowerCase(),
                disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
                visible: !(window.getComputedStyle(el).display === 'none' || window.getComputedStyle(el).visibility === 'hidden')
            })).filter(x => x.visible && !x.disabled)"""
        )
        for item in actions:
            label = _text(item.get("text"))
            lower = label.lower()
            if item.get("type") == "submit" or any(token in lower for token in FINAL_TOKENS):
                return Action("final", label)
        for item in actions:
            label = _text(item.get("text"))
            if label.lower() in ADVANCE_LABELS:
                return Action("advance", label)
        return Action()

    def click_advance(self, action: Action) -> bool:
        self.assert_trusted()
        if action.kind != "advance" or action.label.lower() not in ADVANCE_LABELS:
            return False
        candidates = self._root().get_by_role("button", name=re.compile(rf"^{re.escape(action.label)}$", re.I))
        if candidates.count() == 0:
            candidates = self._root().locator(
                'input[type="button"], input[type="submit"]'
            ).filter(has_text=action.label)
        if candidates.count() == 0:
            return False
        candidates.first.click(timeout=5000)
        try:
            self.page.wait_for_timeout(150)
        except Exception:
            pass
        return True

    def extract_linkedin_jobs(self, limit: int) -> list[dict[str, Any]]:
        self.assert_trusted()
        if urlsplit(self.url).hostname not in {"linkedin.com", "www.linkedin.com"} and not str(
            urlsplit(self.url).hostname or ""
        ).endswith(".linkedin.com"):
            raise OriginPolicyError("LinkedIn discovery requires a LinkedIn origin")
        raw = self.page.locator('a[href*="/jobs/view/"], [data-job-id]').evaluate_all(
            """elements => {
                const seen = new Set(); const jobs = [];
                for (const el of elements) {
                    const anchor = el.matches('a') ? el : el.querySelector('a[href*="/jobs/view/"]');
                    const href = anchor && anchor.href || '';
                    const idMatch = href.match(/\/jobs\/view\/(\d+)/);
                    const id = el.getAttribute('data-job-id') || (idMatch && idMatch[1]) || '';
                    const card = el.closest('li, article, [data-job-id]') || el;
                    const title = (anchor && anchor.innerText) || card.querySelector('[class*="title"]')?.innerText || '';
                    const company = card.querySelector('[class*="company"]')?.innerText || '';
                    const location = card.querySelector('[class*="location"]')?.innerText || '';
                    const key = id || href; if (!key || seen.has(key)) continue; seen.add(key);
                    jobs.push({job_id: id, title, company, location, url: href, source: 'linkedin'});
                }
                return jobs;
            }"""
        )
        return [dict(item) for item in raw[: max(0, int(limit))]]


__all__ = ["ADVANCE_LABELS", "Action", "Control", "PlaywrightPageAdapter"]
''',
    "src/linkedin_apply_assistant/browser_sessions.py": r'''"""Visible Playwright session with strict navigation and deterministic cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Sequence
from urllib.parse import urlsplit

from .contracts import AssistRequest, SearchRequest
from .origin_policy import OriginPolicyError, validate_application_url
from .paths import RuntimePaths, ensure_runtime_dirs
from .safety import BROWSER_PROFILE_WARNING, RISK_STATUSES


AUTH_PATH_MARKERS = ("login", "sign-in", "signin", "checkpoint", "challenge", "captcha", "mfa", "verify")
PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND = "python -m playwright install chromium"


def _page_text(page: Any) -> str:
    for selector in ("body", "html"):
        try:
            text = page.locator(selector).inner_text(timeout=1000)
            if text:
                return str(text)[:20_000]
        except Exception:
            continue
    parts: list[str] = []
    for name in ("title", "text", "body_text", "content"):
        value = getattr(page, name, "")
        try:
            value = value() if callable(value) else value
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    return " ".join(parts)[:20_000]


def page_auth_status(page: Any, *, approved_origins: Sequence[str] = ()) -> str:
    explicit = str(getattr(page, "auth_status", "") or "").strip().lower()
    if explicit in RISK_STATUSES:
        return explicit
    url = str(getattr(page, "url", "") or "")
    decision = validate_application_url(url, approved_origins=approved_origins)
    if not decision.allowed:
        return "blocked_origin"
    try:
        path = urlsplit(url).path.lower()
    except ValueError:
        return "blocked_origin"
    text = f"{path} {_page_text(page)}".lower()
    try:
        if page.locator('input[type="password"]:visible').count() > 0:
            return "login"
    except Exception:
        pass
    if "captcha" in text or "i am not a robot" in text:
        return "captcha"
    if any(token in text for token in ("too many requests", "rate limit", "rate-limit")):
        return "rate_limited"
    if any(token in text for token in ("temporarily restricted", "throttl")):
        return "throttled"
    if any(marker in path for marker in AUTH_PATH_MARKERS):
        if any(marker in path for marker in ("checkpoint", "challenge", "verify")):
            return "checkpoint"
        if "mfa" in path:
            return "mfa"
        return "login"
    return "ready"


def browser_profile_warning() -> str:
    return BROWSER_PROFILE_WARNING


@dataclass
class VisibleBrowserSession:
    context: Any
    close_on_exit: bool = True
    approved_origins: tuple[str, ...] = ()
    _playwright_manager: Any = field(default=None, repr=False)

    @property
    def pages(self) -> Sequence[Any]:
        return list(getattr(self.context, "pages", []) or [])

    def open_url(self, url: str) -> None:
        decision = validate_application_url(
            url,
            approved_origins=self.approved_origins,
            resolve_public_dns=True,
        )
        if not decision.allowed:
            raise OriginPolicyError(decision.reason)
        pages = list(self.pages)
        page = pages[-1] if pages else self.context.new_page()
        page.goto(decision.url, wait_until="domcontentloaded", timeout=30_000)

    def wait_for_change(self, seconds: float) -> None:
        pages = list(self.pages)
        if not pages:
            return
        pages[-1].wait_for_timeout(max(0, int(float(seconds) * 1000)))

    def close(self) -> None:
        try:
            self.context.close()
        finally:
            if self._playwright_manager is not None:
                self._playwright_manager.stop()
                self._playwright_manager = None

    def warnings(self) -> list[str]:
        warnings = [browser_profile_warning()]
        for page in self.pages:
            status = page_auth_status(page, approved_origins=self.approved_origins)
            if status != "ready":
                warnings.append(f"{status} page requires user action in the visible browser")
        return warnings


class VisibleBrowserSessionFactory:
    def __init__(self, paths: RuntimePaths, *, close_on_exit: bool = True) -> None:
        self.paths = paths
        self.close_on_exit = close_on_exit

    def open(self, request: AssistRequest | SearchRequest) -> VisibleBrowserSession:
        ensure_runtime_dirs(self.paths, include_browser_profile=True)
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Browser setup failed: Playwright is required for visible-browser workflows.\n"
                f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND}\n"
                f"Browser profile: {self.paths.browser_profile_dir}"
            ) from exc
        manager = sync_playwright().start()
        try:
            context = manager.chromium.launch_persistent_context(
                str(self.paths.browser_profile_dir),
                headless=False,
                accept_downloads=False,
            )
            context.set_default_timeout(5000)
            context.set_default_navigation_timeout(30_000)
        except Exception as exc:
            manager.stop()
            raise RuntimeError(
                "Browser setup failed: Chromium could not be launched.\n"
                f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND}\n"
                f"Browser profile: {self.paths.browser_profile_dir}"
            ) from exc
        return VisibleBrowserSession(
            context=context,
            close_on_exit=self.close_on_exit,
            approved_origins=tuple(getattr(request, "approved_origins", ()) or ()),
            _playwright_manager=manager,
        )

    @staticmethod
    def auth_status(page: Any) -> str:
        return page_auth_status(page)


__all__ = [
    "PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND", "VisibleBrowserSession", "VisibleBrowserSessionFactory",
    "browser_profile_warning", "page_auth_status",
]
''',
    "src/linkedin_apply_assistant/page_actions.py": r'''"""Origin-safe page operations used by form adapters."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from .browser_adapter import PlaywrightPageAdapter


LOGGER = logging.getLogger(__name__)


def safe_count(target: Any) -> int:
    try:
        count = target.count
        return int(count() if callable(count) else count)
    except Exception as exc:
        LOGGER.debug("locator count failed", exc_info=exc)
        return 0


def safe_visible(target: Any) -> bool:
    try:
        visible = target.is_visible
        return bool(visible() if callable(visible) else visible)
    except Exception as exc:
        LOGGER.debug("locator visibility failed", exc_info=exc)
        return safe_count(target) > 0


def _first_locator(page: Any, selectors: Iterable[str], *, require_visible: bool = True) -> Any | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if safe_count(locator) > 0 and (not require_visible or safe_visible(locator)):
                return locator
        except Exception as exc:
            LOGGER.debug("selector failed: %s", selector, exc_info=exc)
    return None


def fill_first(page: Any, selectors: Iterable[str], value: Any) -> bool:
    if value is None or str(value).strip() == "":
        return False
    if hasattr(page, "fill_field"):
        return bool(page.fill_field(tuple(selectors), str(value)))
    locator = _first_locator(page, selectors)
    if locator is None:
        return False
    try:
        current = locator.input_value(timeout=1000)
        if str(current or "").strip():
            return True
    except Exception:
        pass
    try:
        locator.fill(str(value), timeout=3000)
        return True
    except Exception as exc:
        LOGGER.warning("Unable to fill a reviewed form field: %s", exc)
        return False


def set_file_first(page: Any, selectors: Iterable[str], path: str | Path) -> bool:
    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 10 * 1024 * 1024:
        return False
    if hasattr(page, "set_file"):
        return bool(page.set_file(tuple(selectors), target))
    locator = _first_locator(page, selectors, require_visible=False)
    if locator is None:
        return False
    try:
        locator.set_input_files(str(target), timeout=5000)
        return True
    except Exception as exc:
        LOGGER.warning("Unable to attach reviewed document %s: %s", target.name, exc)
        return False


def visible_questions(page: Any) -> list[dict[str, Any]]:
    questions = getattr(page, "visible_questions", None)
    if questions is None:
        questions = getattr(page, "questions", None)
    if callable(questions):
        questions = questions()
    if questions:
        return [dict(item) if isinstance(item, dict) else {"question": str(item)} for item in questions]
    if hasattr(page, "locator"):
        return [
            {
                "question": control.label,
                "field_type": control.field_type,
                "required": control.required,
                "control_id": control.control_id,
            }
            for control in PlaywrightPageAdapter(page).controls()
            if control.label and control.field_type not in {"hidden", "file", "submit", "button"}
        ]
    return []


def fill_question(page: Any, question: dict[str, Any], answer: Any) -> bool:
    if answer is None or str(answer).strip() == "":
        return False
    if hasattr(page, "fill_question"):
        return bool(page.fill_question(question, str(answer)))
    if hasattr(page, "locator") and question.get("control_id"):
        adapter = PlaywrightPageAdapter(page)
        control = next(
            (item for item in adapter.controls() if item.control_id == question["control_id"]),
            None,
        )
        return bool(control and adapter.fill_control(control, answer))
    return False


def required_documents(page: Any) -> set[str]:
    value = getattr(page, "required_documents", None)
    if callable(value):
        value = value()
    if value is not None:
        return {str(item) for item in value or set()}
    if hasattr(page, "locator"):
        required: set[str] = set()
        for control in PlaywrightPageAdapter(page).controls():
            if control.field_type == "file" and control.required:
                label = f"{control.label} {control.name}".lower()
                required.add("cover_letter" if "cover" in label else "resume")
        return required
    return set()


__all__ = [
    "fill_first", "fill_question", "required_documents", "safe_count", "safe_visible",
    "set_file_first", "visible_questions",
]
''',
    "src/linkedin_apply_assistant/ats_handlers.py": r'''"""Origin-verified, no-submit ATS form handling."""

from __future__ import annotations

from typing import Any

from .browser_adapter import PlaywrightPageAdapter
from .form_engine import FillResult, detect_ats, normalize_space
from .origin_policy import validate_application_url
from .page_actions import fill_first, fill_question, required_documents, set_file_first, visible_questions
from .page_selectors import DOCUMENT_SELECTORS, PROFILE_FIELD_SELECTORS
from .qa_bank import QABank
from .safety import DISABLED_SUBMISSION_REASON, DisabledSubmissionPolicy


__all__ = ["DisabledSubmissionPolicy"]

DETECTED_ATS = (
    "greenhouse", "lever", "ashby", "workday", "smartrecruiters", "recruitee", "workable",
    "bamboohr", "icims", "taleo", "successfactors", "personio", "teamtailor", "jobvite", "resumator",
)
SPECIALIZED_ATS = ("greenhouse", "lever", "ashby")
SUPPORTED_ATS = (*DETECTED_ATS, "generic")


def normalize_ats(value: str | None, *, url: str | None = None) -> str:
    candidate = (value or "").strip().lower() or (detect_ats(url or "") if url else "")
    return "generic" if candidate in {"", "unknown"} else candidate


def is_supported_ats(value: str | None) -> bool:
    return normalize_ats(value) in SUPPORTED_ATS


def _profile_value(profile: dict[str, Any], key: str) -> Any:
    if key == "full_name":
        return profile.get("full_name") or " ".join(
            part for part in (normalize_space(profile.get("first_name")), normalize_space(profile.get("last_name"))) if part
        )
    return profile.get(key)


def _fake_fill(
    page: Any,
    adapter_key: str,
    profile: dict[str, Any],
    bank: QABank | None,
    context: dict[str, Any],
    documents: dict[str, Any],
) -> FillResult:
    filled: list[str] = []
    fields = PROFILE_FIELD_SELECTORS.get(adapter_key) or PROFILE_FIELD_SELECTORS["generic"]
    for key, selectors in fields.items():
        if fill_first(page, selectors, _profile_value(profile, key)):
            filled.append(key)
    missing: list[Any] = []
    required = required_documents(page)
    for kind, selectors in DOCUMENT_SELECTORS.items():
        configured = documents.get(kind) or documents.get(f"{kind}_path")
        if configured and set_file_first(page, selectors, configured):
            filled.append(f"document:{kind}")
        elif kind in required:
            missing.append(f"{kind} document path is required but not configured or readable.")
    unknown: list[Any] = []
    for question in visible_questions(page):
        label = normalize_space(question.get("question") or question.get("label"))
        if not label:
            continue
        field_type = normalize_space(question.get("field_type") or "text")
        required_question = bool(question.get("required"))
        answer = bank.find_answer(label, field_type=field_type, context=context) if bank else None
        if answer and fill_question(page, question, answer.get("answer")):
            filled.append(f"question:{label}")
        else:
            pending = bank.log_pending(
                label, context=context, field_type=field_type, is_required=required_question
            ) if bank else {"question": label, "field_type": field_type, "required": required_question}
            unknown.append(pending)
            if required_question:
                missing.append(label)
    return FillResult(
        filled=filled,
        required_empty=missing,
        unknown_questions=unknown,
        reached_submit_step=bool(getattr(page, "at_submit_step", False)),
        surface=f"external:{adapter_key}",
    )


def fill_external_apply_page(
    page: Any,
    ats: str,
    profile: dict[str, Any],
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
    documents: dict[str, Any] | None = None,
) -> FillResult:
    normalized = normalize_ats(ats, url=str(getattr(page, "url", "") or ""))
    if page is None:
        return FillResult(
            required_empty=["A browser page object is required before filling can run."],
            surface=f"external:{normalized}",
        )
    context = dict(qa_context or {})
    approved = tuple(context.get("approved_origins") or ())
    url = str(getattr(page, "url", "") or context.get("apply_url") or "")
    decision = validate_application_url(url, expected_ats=normalized, approved_origins=approved)
    if not decision.allowed:
        return FillResult(
            required_empty=[f"Blocked untrusted application origin: {decision.reason}"],
            surface=f"external:{normalized}",
        )
    context.update({"ats": normalized, "domain": decision.hostname, "apply_url": decision.url})
    if hasattr(page, "locator"):
        result = PlaywrightPageAdapter(
            page, expected_ats=normalized, approved_origins=approved
        ).fill_surface(profile, bank, context, documents)
        return FillResult(
            filled=result["filled"],
            required_empty=result["required_empty"],
            unknown_questions=result["unknown_questions"],
            reached_submit_step=PlaywrightPageAdapter(
                page, expected_ats=normalized, approved_origins=approved
            ).next_action().kind == "final",
            surface=f"external:{normalized if normalized in SPECIALIZED_ATS else 'generic'}",
        )
    key = normalized if normalized in SPECIALIZED_ATS else "generic"
    return _fake_fill(page, key, profile, bank, context, dict(documents or {}))


def submit_disabled_status() -> tuple[bool, str]:
    return False, DISABLED_SUBMISSION_REASON
''',
    "src/linkedin_apply_assistant/linkedin_layer.py": r'''"""LinkedIn discovery and multi-step fill-only browser integration."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, unquote, urlsplit, urlunsplit

from .ats_handlers import fill_external_apply_page
from .browser_adapter import PlaywrightPageAdapter
from .browser_sessions import page_auth_status
from .form_engine import DetectionResult, FillResult, detect_ats, normalize_space
from .origin_policy import OriginPolicyError, canonical_https_url, is_linkedin_host, validate_application_url
from .page_actions import fill_first, fill_question, required_documents, set_file_first, visible_questions
from .page_selectors import DOCUMENT_SELECTORS, EASY_APPLY_ACTIONS, PROFILE_FIELD_SELECTORS
from .qa_bank import QABank


DEFAULT_SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def sanitize_linkedin_search_url(search_url: str | None) -> str:
    try:
        url = canonical_https_url(search_url or DEFAULT_SEARCH_URL)
        parsed = urlsplit(url)
    except OriginPolicyError:
        return DEFAULT_SEARCH_URL
    if not is_linkedin_host(parsed.hostname):
        return DEFAULT_SEARCH_URL
    query = parse_qs(parsed.query, keep_blank_values=False)
    query.pop("currentJobId", None)
    query.pop("start", None)
    return urlunsplit(("https", parsed.netloc, parsed.path or "/jobs/search/", urlencode(query, doseq=True), ""))


def linkedin_search_url_for_job(search_url: str, job_id: str) -> str:
    parsed = urlsplit(sanitize_linkedin_search_url(search_url))
    query = parse_qs(parsed.query)
    query["currentJobId"] = [str(job_id)]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))


def linkedin_job_id_from_job_record(job: dict[str, Any]) -> str:
    for key in ("job_id", "linkedin_job_id", "id"):
        value = normalize_space(job.get(key))
        if value:
            return value
    url = str(job.get("url") or job.get("linkedin_url") or "")
    match = re.search(r"/jobs/view/(\d+)", url) or re.search(r"[?&]currentJobId=(\d+)", url)
    return match.group(1) if match else ""


def _decode_linkedin_apply_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if not is_linkedin_host(parsed.hostname):
        return url
    query = parse_qs(parsed.query)
    for key in ("url", "dest", "destination", "redirect"):
        if query.get(key):
            return unquote(query[key][0])
    return ""


def _external_apply_url_candidate(url: str, *, require_apply_signal: bool = False) -> str:
    decoded = _decode_linkedin_apply_url(url)
    decision = validate_application_url(decoded, allow_linkedin=False)
    if not decision.allowed or decision.ats == "linkedin":
        return ""
    haystack = f"{decision.hostname} {urlsplit(decision.url).path}".lower()
    if require_apply_signal and decision.ats == "unknown" and not any(
        token in haystack for token in ("apply", "job", "career", "position", "opening")
    ):
        return ""
    return decision.url


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value)


def _external_apply_url_from_html(markup: str) -> str:
    parser = _HrefParser()
    parser.feed(str(markup or "")[:1_000_000])
    for href in parser.hrefs:
        candidate = _external_apply_url_candidate(href, require_apply_signal=True)
        if candidate:
            return candidate
    return ""


def current_linkedin_job_info(page: Any, card: Any | None = None) -> dict[str, str]:
    if isinstance(card, dict):
        return {
            "title": normalize_space(card.get("title")), "company": normalize_space(card.get("company")),
            "url": normalize_space(card.get("url")), "job_id": linkedin_job_id_from_job_record(card),
        }
    return {"title": "", "company": "", "url": "", "job_id": ""}


def detect_current_apply_surface(
    context: Any,
    profile: dict[str, Any] | None = None,
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
) -> DetectionResult:
    _ = profile, bank
    pages = getattr(context, "pages", None) or []
    approved = tuple((qa_context or {}).get("approved_origins") or ())
    for page in reversed(list(pages)):
        url = str(getattr(page, "url", "") or "")
        page_context = dict(qa_context or {})
        page_context.setdefault("apply_url", url)
        for key in ("job_id", "company", "role", "title"):
            value = getattr(page, key, "")
            if value and key not in page_context:
                page_context[key] = value
        status = page_auth_status(page, approved_origins=approved)
        if status != "ready":
            page_context["blocked_reason"] = f"{status} page requires user action"
            return DetectionResult("browser_blocked", page, "linkedin" if is_linkedin_host(urlsplit(url).hostname) else "", page_context)
        if hasattr(page, "locator"):
            decision = validate_application_url(url, approved_origins=approved)
            if not decision.allowed:
                page_context["blocked_reason"] = decision.reason
                return DetectionResult("browser_blocked", page, "", page_context)
            try:
                dialogs = page.locator('[role="dialog"]:visible')
                easy_apply = dialogs.count() > 0 and dialogs.last.locator("input, select, textarea").count() > 0
            except Exception:
                easy_apply = False
            if is_linkedin_host(decision.hostname) and easy_apply:
                page_context["ats"] = "linkedin"
                return DetectionResult("linkedin_easy_apply", page, "linkedin", page_context)
            ats = detect_ats(url)
            try:
                has_form = page.locator("form input, form select, form textarea").count() > 0
            except Exception:
                has_form = False
            if ats != "unknown" or has_form:
                page_context["ats"] = ats if ats != "unknown" else "generic"
                return DetectionResult("external_ats", page, page_context["ats"], page_context)
        if bool(getattr(page, "easy_apply_open", False)) or getattr(page, "surface", "") == "linkedin_easy_apply":
            return DetectionResult("linkedin_easy_apply", page, "linkedin", page_context)
        ats = detect_ats(url)
        if ats != "unknown":
            page_context["ats"] = ats
            return DetectionResult("external_ats", page, ats, page_context)
        if bool(getattr(page, "has_form", False)) and str(urlsplit(url).hostname or "").endswith(".test"):
            page_context["ats"] = "generic"
            page_context["approved_origins"] = [f"https://{urlsplit(url).hostname}"]
            return DetectionResult("external_ats", page, "generic", page_context)
    return DetectionResult(surface="none", job_context=dict(qa_context or {}))


class CurrentSurfaceDetector:
    def __init__(self, *, profile: dict[str, Any] | None = None, bank: QABank | None = None, qa_context: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}
        self.bank = bank
        self.qa_context = qa_context or {}

    def detect(self, session: Any) -> DetectionResult:
        context = dict(self.qa_context)
        context.setdefault("approved_origins", tuple(getattr(session, "approved_origins", ()) or ()))
        return detect_current_apply_surface(session, self.profile, self.bank, context)


class CurrentSurfaceFillAdapter:
    def fill(self, detection: DetectionResult, profile: dict[str, Any], bank: QABank | None = None, qa_context: dict[str, Any] | None = None, documents: dict[str, Any] | None = None) -> FillResult:
        return fill_current_surface(detection, profile, bank, qa_context, documents)


def fill_current_surface(detection: DetectionResult, profile: dict[str, Any], bank: QABank | None = None, qa_context: dict[str, Any] | None = None, documents: dict[str, Any] | None = None) -> FillResult:
    merged = dict(detection.job_context)
    merged.update(qa_context or {})
    if detection.surface == "external_ats":
        return fill_external_apply_page(detection.page, detection.ats, profile, bank, merged, documents)
    if detection.surface == "linkedin_easy_apply":
        return fill_linkedin_easy_apply(detection.page, profile, bank, merged, documents=documents)
    return FillResult(surface=detection.surface)


def _fill_fake_easy(page: Any, profile: dict[str, Any], bank: QABank | None, context: dict[str, Any], documents: dict[str, Any]) -> FillResult:
    filled: list[str] = []
    for key, selectors in PROFILE_FIELD_SELECTORS["linkedin_easy_apply"].items():
        value = profile.get(key)
        if key == "full_name" and not value:
            value = " ".join(part for part in (normalize_space(profile.get("first_name")), normalize_space(profile.get("last_name"))) if part)
        if fill_first(page, selectors, value):
            filled.append(key)
    missing: list[Any] = []
    for kind, selectors in DOCUMENT_SELECTORS.items():
        value = documents.get(kind) or documents.get(f"{kind}_path")
        if value and set_file_first(page, selectors, value):
            filled.append(f"document:{kind}")
        elif kind in required_documents(page):
            missing.append(f"{kind} document path is required but not configured.")
    unknown: list[Any] = []
    for question in visible_questions(page):
        text = normalize_space(question.get("question") or question.get("label"))
        required = bool(question.get("required"))
        answer = bank.find_answer(text, field_type=question.get("field_type"), context=context) if bank else None
        if answer and fill_question(page, question, answer.get("answer")):
            filled.append(f"question:{text}")
        else:
            pending = bank.log_pending(text, context=context, field_type=question.get("field_type"), is_required=required) if bank else {"question": text, "required": required}
            unknown.append(pending)
            if required:
                missing.append(text)
    reached = False
    if not missing:
        for _ in range(5):
            action = normalize_space(page.next_easy_apply_action()).lower() if hasattr(page, "next_easy_apply_action") else "final" if getattr(page, "at_submit_step", False) else ""
            if "submit" in action or action in {item.lower() for item in EASY_APPLY_ACTIONS["final"]}:
                reached = True
                break
            if action in {item.lower() for item in EASY_APPLY_ACTIONS["advance"]} and hasattr(page, "advance_easy_apply"):
                if not page.advance_easy_apply(action):
                    break
                filled.append(f"advanced:{action}")
            else:
                break
    return FillResult(filled, missing, unknown, reached, "linkedin_easy_apply")


def fill_linkedin_easy_apply(
    page: Any,
    profile: dict[str, Any],
    bank: QABank | None = None,
    qa_context: dict[str, Any] | None = None,
    easy_btn: Any | None = None,
    documents: dict[str, Any] | None = None,
) -> FillResult:
    _ = easy_btn
    context = dict(qa_context or {})
    docs = dict(documents or {})
    if not hasattr(page, "locator"):
        return _fill_fake_easy(page, profile, bank, context, docs)
    approved = tuple(context.get("approved_origins") or ())
    filled: list[Any] = []
    missing: list[Any] = []
    unknown: list[Any] = []
    reached = False
    for _ in range(max(1, min(int(context.get("max_steps", 5)), 10))):
        adapter = PlaywrightPageAdapter(page, expected_ats="linkedin", approved_origins=approved)
        step = adapter.fill_surface(profile, bank, {**context, "ats": "linkedin"}, docs)
        filled.extend(item for item in step["filled"] if item not in filled)
        missing.extend(item for item in step["required_empty"] if item not in missing)
        unknown.extend(step["unknown_questions"])
        if missing:
            break
        action = adapter.next_action()
        if action.kind == "final":
            reached = True
            break
        if action.kind != "advance" or not adapter.click_advance(action):
            break
        filled.append(f"advanced:{action.label.lower()}")
    return FillResult(filled, missing, unknown, reached, "linkedin_easy_apply")


class StaticLinkedInDiscovery:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []

    def discover(self, request: Any) -> list[dict[str, Any]]:
        return list(self.records)


class BrowserLinkedInDiscovery:
    def __init__(self, session_factory: Any | None = None) -> None:
        self.session_factory = session_factory

    def discover(self, request: Any) -> list[dict[str, Any]]:
        if self.session_factory is None:
            raise RuntimeError("Live LinkedIn discovery requires a configured browser session factory.")
        session = self.session_factory.open(request)
        try:
            session.open_url(request.search_url or DEFAULT_SEARCH_URL)
            pages = list(getattr(session, "pages", []) or [])
            if not pages:
                return []
            page = pages[-1]
            if hasattr(page, "linkedin_jobs"):
                return list(page.linkedin_jobs(limit=request.limit))
            return PlaywrightPageAdapter(page, expected_ats="linkedin").extract_linkedin_jobs(request.limit)
        finally:
            if getattr(session, "close_on_exit", False):
                session.close()


def run_linkedin_search_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    return {"status": "not_configured", "reason": "Use the package search workflow with discovery."}


def run_linkedin_json_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    return {"status": "disabled", "reason": "JSON browser orchestration is not enabled."}


def run_assistive_flow(*args: Any, **kwargs: Any) -> dict[str, str]:
    return {"status": "not_configured", "reason": "Use the package assist workflow with a session factory."}
''',
    "src/linkedin_apply_assistant/workflows.py": r'''"""Bounded search and assist lifecycle orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from .contracts import (
    AssistEvent, AssistRequest, AssistResult, BrowserSession, BrowserSessionFactory, FillAdapter,
    JobRecord, LinkedInDiscovery, ReportArtifact, ReportSink, SearchRequest, SearchResult,
    SubmissionPolicy, SurfaceIdentity,
)
from .form_engine import DetectionResult, FillResult, normalize_space
from .linkedin_layer import DEFAULT_SEARCH_URL, sanitize_linkedin_search_url
from .origin_policy import canonical_https_url
from .safety import backoff_delay, clamp_assist_cycles, clamp_search_limit, domain_from_url, normalize_url_for_audit


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_search_url(request: SearchRequest) -> str:
    if request.search_url:
        return sanitize_linkedin_search_url(request.search_url)
    parsed = urlsplit(DEFAULT_SEARCH_URL)
    query: dict[str, list[str]] = {}
    if request.query:
        query["keywords"] = [normalize_space(request.query)]
    if request.location:
        query["location"] = [normalize_space(request.location)]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))


def normalized_job_url(url: str) -> str:
    try:
        parsed = urlsplit(canonical_https_url(url))
    except Exception:
        return ""
    query = parse_qs(parsed.query)
    for key in ("trk", "refId", "trackingId", "position", "pageNum"):
        query.pop(key, None)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), urlencode(query, doseq=True), ""))


def job_from_record(record: JobRecord | Mapping[str, Any], *, search_url: str = "") -> JobRecord:
    if isinstance(record, JobRecord):
        return record if record.search_url or not search_url else JobRecord(**{**record.__dict__, "search_url": search_url})
    from .schemas import normalize_job_record

    normalized = normalize_job_record(dict(record))
    return JobRecord(
        job_id=normalized["job_id"], title=normalized["title"], company=normalized["company"],
        url=normalized["url"], location=normalized["location"], source=normalized["source"],
        search_url=normalized["search_url"] or search_url, ats=normalized["ats"], raw=dict(record),
    )


def dedupe_jobs(records: Sequence[JobRecord | Mapping[str, Any]], *, search_url: str) -> list[JobRecord]:
    seen: set[str] = set()
    jobs: list[JobRecord] = []
    for record in records:
        try:
            job = job_from_record(record, search_url=search_url)
        except ValueError:
            continue
        normalized_url = normalized_job_url(job.url)
        if not job.job_id and not normalized_url:
            continue
        key = f"id:{job.job_id}" if job.job_id else f"url:{normalized_url}"
        if key in seen:
            continue
        seen.add(key)
        jobs.append(job)
    return jobs


def _job_payload(job: JobRecord) -> dict[str, Any]:
    url = normalize_url_for_audit(job.url)
    return {
        "job_id": job.job_id, "title": job.title, "company": job.company, "url": url,
        "domain": domain_from_url(url), "location": job.location, "source": job.source,
        "search_url": normalize_url_for_audit(job.search_url), "ats": job.ats,
    }


def _report_artifacts(value: Sequence[ReportArtifact] | None) -> list[ReportArtifact]:
    return list(value or [])


def run_search_workflow(
    request: SearchRequest,
    discovery: LinkedInDiscovery,
    report_sink: ReportSink,
    submission_policy: SubmissionPolicy | None = None,
) -> SearchResult:
    _ = submission_policy
    run_id = uuid4().hex
    search_url = build_search_url(request)
    effective_limit = clamp_search_limit(request.limit)
    records: Sequence[JobRecord | Mapping[str, Any]] = []
    if effective_limit:
        records = discovery.discover(
            SearchRequest(
                limit=effective_limit, search_url=search_url, query=request.query, location=request.location,
                profile=dict(request.profile), approved_origins=tuple(request.approved_origins), paths=request.paths,
            )
        )
    jobs = dedupe_jobs(records, search_url=search_url)[:effective_limit]
    timestamp = utc_timestamp()
    events = [
        {
            "type": "job", "action": "discovered", "status": "recorded", "surface": "linkedin_search",
            "ats": job.ats, "blocked_reason": "", "unknown_questions": [], "required_empty_count": 0,
            **_job_payload(job),
        }
        for job in jobs
    ]
    summary = {
        "command": "search", "requested_limit": request.limit, "effective_limit": effective_limit,
        "discovered": len(records), "deduplicated": len(jobs), "submitted": 0,
    }
    report = {
        "schema_version": 1, "run_id": run_id, "command": "search", "timestamp": timestamp,
        "search_url": normalize_url_for_audit(search_url), "jobs": [_job_payload(job) for job in jobs],
        "events": events, "summary": summary,
    }
    artifacts = _report_artifacts(report_sink.write("search", report))
    return SearchResult(timestamp=timestamp, search_url=search_url, jobs=jobs, events=events, summary=summary, reports=artifacts)


def surface_identity_from_detection(detection: DetectionResult) -> SurfaceIdentity:
    page = detection.page
    url = normalize_url_for_audit(getattr(page, "url", "") if page is not None else "")
    title_attr = getattr(page, "title", "")
    try:
        title = title_attr() if callable(title_attr) else title_attr
    except Exception:
        title = ""
    context = dict(detection.job_context or {})
    return SurfaceIdentity(
        url=url or normalize_url_for_audit(context.get("apply_url") or context.get("url")),
        title=normalize_space(title or context.get("title") or context.get("role")),
        surface=normalize_space(detection.surface), ats=normalize_space(detection.ats),
        job_id=normalize_space(context.get("job_id")),
    )


def _assist_event(event_type: str, detection: DetectionResult, result: FillResult, identity: SurfaceIdentity, *, status: str, blocked_reason: str = "") -> AssistEvent:
    return AssistEvent(
        type=event_type, surface=detection.surface, ats=detection.ats, status=status,
        filled_count=len(result.filled), required_empty_count=len(result.required_empty),
        unknown_count=len(result.unknown_questions), reached_submit_step=bool(result.reached_submit_step),
        blocked_reason=blocked_reason, job=dict(detection.job_context or {}), identity=identity,
        required_empty=list(result.required_empty), unknown_questions=list(result.unknown_questions),
        timestamp=utc_timestamp(),
    )


def _bounded_job_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    ctx = dict(context or {})
    url = normalize_url_for_audit(ctx.get("apply_url") or ctx.get("url"))
    return {
        "job_id": normalize_space(ctx.get("job_id")), "company": normalize_space(ctx.get("company")),
        "role": normalize_space(ctx.get("role") or ctx.get("title")),
        "title": normalize_space(ctx.get("title") or ctx.get("role")), "url": url,
        "domain": domain_from_url(url or ctx.get("domain")), "ats": normalize_space(ctx.get("ats")),
    }


def _event_payload(event: AssistEvent) -> dict[str, Any]:
    identity = event.identity
    return {
        "type": event.type, "action": event.type, "timestamp": event.timestamp, "surface": event.surface,
        "ats": event.ats, "status": event.status, "filled_count": event.filled_count,
        "required_empty_count": event.required_empty_count, "unknown_count": event.unknown_count,
        "reached_submit_step": event.reached_submit_step, "blocked_reason": event.blocked_reason,
        "job": _bounded_job_context(event.job),
        "identity": {} if identity is None else {
            "url": normalize_url_for_audit(identity.url), "domain": domain_from_url(identity.url),
            "title": identity.title, "surface": identity.surface, "ats": identity.ats, "job_id": identity.job_id,
        },
        "required_empty": list(event.required_empty),
        "unknown_questions": [
            {
                "question": normalize_space(item.get("question")), "field_type": normalize_space(item.get("field_type") or "text"),
                "required": bool(item.get("required")), "ats": normalize_space(item.get("ats")),
                "company": normalize_space(item.get("company")), "role": normalize_space(item.get("role") or item.get("title")),
                "domain": normalize_space(item.get("domain")),
            } if isinstance(item, Mapping) else normalize_space(item)
            for item in event.unknown_questions
        ],
        "feedback": compact_assist_feedback(event),
    }


def compact_assist_feedback(event: AssistEvent) -> str:
    return (
        f"{event.surface or 'none'}/{event.ats or 'unknown'} status={event.status or 'unknown'} "
        f"filled={event.filled_count} required_empty={event.required_empty_count} "
        f"unknown={event.unknown_count} submit_step={str(event.reached_submit_step).lower()}"
    )


def run_assist_workflow(
    request: AssistRequest,
    session_factory: BrowserSessionFactory,
    detector: Any,
    fill_adapter: FillAdapter,
    report_sink: ReportSink,
    submission_policy: SubmissionPolicy | None = None,
    bank: Any = None,
) -> AssistResult:
    if request.mode not in {"auto-watch", "on-demand"}:
        raise ValueError("assist mode must be auto-watch or on-demand")
    run_id = uuid4().hex
    session: BrowserSession | None = None
    events: list[AssistEvent] = []
    seen: set[str] = set()
    timestamp = utc_timestamp()
    try:
        session = session_factory.open(request)
        if request.start_url:
            session.open_url(request.start_url)
        cycles = clamp_assist_cycles(request.max_cycles)
        for attempt in range(cycles):
            detection = detector.detect(session)
            if detection.surface == "none":
                if request.mode == "on-demand":
                    break
            else:
                identity = surface_identity_from_detection(detection)
                if detection.surface == "browser_blocked":
                    reason = normalize_space(detection.job_context.get("blocked_reason") or "Visible browser requires user action.")
                    events.append(_assist_event("blocked", detection, FillResult(surface=detection.surface), identity, status="blocked", blocked_reason=reason))
                    break
                if identity.key() in seen:
                    events.append(AssistEvent(type="skipped", surface=detection.surface, ats=detection.ats, status="duplicate", job=dict(detection.job_context or {}), identity=identity, timestamp=utc_timestamp()))
                else:
                    seen.add(identity.key())
                    result = fill_adapter.fill(
                        detection, dict(request.profile), bank, {**request.qa_context, "max_steps": request.max_steps, "approved_origins": request.approved_origins}, dict(request.documents)
                    )
                    status = "blocked" if result.required_empty else "review_required" if result.reached_submit_step else "filled"
                    reason = "; ".join(str(item) for item in result.required_empty)
                    if result.reached_submit_step and submission_policy is not None:
                        decision = submission_policy.decide("submit", dict(detection.job_context or {}))
                        reason = decision.reason
                    events.append(_assist_event("filled", detection, result, identity, status=status, blocked_reason=reason))
                    if status in {"blocked", "review_required"}:
                        break
            if request.mode == "on-demand":
                break
            wait = getattr(session, "wait_for_change", None)
            if callable(wait) and attempt + 1 < cycles:
                wait(max(float(request.poll_seconds), backoff_delay(attempt + 1)))
    finally:
        if session is not None and getattr(session, "close_on_exit", False):
            session.close()
    summary = {
        "command": "assist", "mode": request.mode, "requested_cycles": request.max_cycles,
        "effective_cycles": clamp_assist_cycles(request.max_cycles), "events": len(events),
        "filled": sum(event.status in {"filled", "review_required"} for event in events),
        "blocked": sum(event.status == "blocked" for event in events),
        "duplicates": sum(event.status == "duplicate" for event in events),
        "required_empty": sum(event.required_empty_count for event in events),
        "unknown_questions": sum(event.unknown_count for event in events), "submitted": 0,
    }
    report = {"schema_version": 1, "run_id": run_id, "command": "assist", "timestamp": timestamp, "events": [_event_payload(event) for event in events], "summary": summary}
    artifacts = _report_artifacts(report_sink.write("assist", report))
    return AssistResult(timestamp=timestamp, events=events, summary=summary, reports=artifacts)
''',
}


def apply() -> None:
    for relative, content in FILES.items():
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
