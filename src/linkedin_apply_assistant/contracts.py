"""Stable workflow contracts for the standalone assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .form_engine import DetectionResult, FillResult


@dataclass(frozen=True)
class JobRecord:
    """Plain-value LinkedIn job context used by workflow reports."""

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
    """Inputs for a search-only workflow run."""

    limit: int = 10
    search_url: str | None = None
    query: str | None = None
    location: str | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    paths: Any = None


@dataclass(frozen=True)
class SurfaceIdentity:
    """Stable identity for a visible application surface."""

    url: str = ""
    title: str = ""
    surface: str = ""
    ats: str = ""
    job_id: str = ""

    def key(self) -> str:
        """Return a compact key for fill-once session deduplication."""

        return "|".join((self.url, self.title, self.surface, self.ats, self.job_id))


@dataclass(frozen=True)
class ReportArtifact:
    """One report file produced by a workflow."""

    kind: str
    path: Path


@dataclass
class SearchResult:
    """Search workflow output and report metadata."""

    command: str = "search"
    timestamp: str = ""
    search_url: str = ""
    jobs: list[JobRecord] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    reports: list[ReportArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class AssistEvent:
    """One assistive fill workflow event."""

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
    """Inputs for a visible-browser assistive fill session."""

    start_url: str | None = None
    mode: str = "auto"
    max_cycles: int = 1
    profile: dict[str, Any] = field(default_factory=dict)
    qa_context: dict[str, Any] = field(default_factory=dict)
    documents: dict[str, Any] = field(default_factory=dict)
    paths: Any = None


@dataclass
class AssistResult:
    """Assist workflow output and report metadata."""

    command: str = "assist"
    timestamp: str = ""
    events: list[AssistEvent] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    reports: list[ReportArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResult:
    """Read-only submission policy decision."""

    status: str = "disabled"
    reason: str = "Browser submission is disabled in this package boundary."
    allowed: bool = False


@dataclass(frozen=True)
class SubmitDecision:
    """Plain-value audit record for an explicit submit/apply boundary."""

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
    """Visible browser session abstraction."""

    @property
    def pages(self) -> Sequence[Any]:
        """Return pages or tabs known to the session."""

    def open_url(self, url: str) -> None:
        """Open a URL in the visible session."""

    def close(self) -> None:
        """Close the session when the caller owns it."""


class BrowserSessionFactory(Protocol):
    """Factory that creates visible browser sessions."""

    def open(self, request: AssistRequest | SearchRequest) -> BrowserSession:
        """Open a session for a workflow request."""


class LinkedInDiscovery(Protocol):
    """LinkedIn search result discovery boundary."""

    def discover(self, request: SearchRequest) -> Sequence[JobRecord | Mapping[str, Any]]:
        """Return candidate job records for a search request."""


class ApplySurfaceDetector(Protocol):
    """Current apply surface detection boundary."""

    def detect(self, session: BrowserSession) -> DetectionResult:
        """Detect the currently fillable application surface."""


class FillAdapter(Protocol):
    """Fill-only adapter boundary."""

    def fill(
        self,
        detection: DetectionResult,
        profile: dict[str, Any],
        bank: Any = None,
        qa_context: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
    ) -> FillResult:
        """Fill a detected surface without performing submission."""


class QAMatcher(Protocol):
    """Q&A matching boundary."""

    def find_answer(
        self,
        question_text: str,
        field_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Find an answer for a question."""

    def log_pending(
        self,
        question_text: str,
        context: dict[str, Any] | None = None,
        field_type: str | None = None,
        is_required: bool = False,
    ) -> dict[str, Any]:
        """Record an unknown question."""


class SubmissionPolicy(Protocol):
    """Submission policy boundary."""

    def decide(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> SubmissionResult:
        """Return whether an action is allowed."""


class ReportSink(Protocol):
    """Workflow report writing boundary."""

    def write(self, command: str, report: dict[str, Any]) -> Sequence[ReportArtifact]:
        """Write report artifacts for a workflow command."""


__all__ = [
    "ApplySurfaceDetector",
    "AssistEvent",
    "AssistRequest",
    "AssistResult",
    "BrowserSession",
    "BrowserSessionFactory",
    "FillAdapter",
    "JobRecord",
    "LinkedInDiscovery",
    "QAMatcher",
    "ReportArtifact",
    "ReportSink",
    "SearchRequest",
    "SearchResult",
    "SubmissionPolicy",
    "SubmissionResult",
    "SubmitDecision",
    "SurfaceIdentity",
]
