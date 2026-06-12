"""Selector-light workflow orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .contracts import (
    AssistEvent,
    AssistRequest,
    AssistResult,
    BrowserSession,
    BrowserSessionFactory,
    FillAdapter,
    JobRecord,
    LinkedInDiscovery,
    ReportArtifact,
    ReportSink,
    SearchRequest,
    SearchResult,
    SubmissionPolicy,
    SurfaceIdentity,
)
from .form_engine import DetectionResult, FillResult, normalize_space
from .linkedin_layer import DEFAULT_SEARCH_URL, sanitize_linkedin_search_url
from .safety import (
    clamp_assist_cycles,
    clamp_search_limit,
    domain_from_url,
    normalize_url_for_audit,
)


def utc_timestamp() -> str:
    """Return an ISO timestamp for reports."""

    return datetime.now(timezone.utc).isoformat()


def build_search_url(request: SearchRequest) -> str:
    """Build or sanitize the LinkedIn jobs search URL for a request."""

    if request.search_url:
        return sanitize_linkedin_search_url(request.search_url)

    parsed = urlparse(DEFAULT_SEARCH_URL)
    query: dict[str, list[str]] = {}
    if request.query:
        query["keywords"] = [request.query]
    if request.location:
        query["location"] = [request.location]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def normalized_job_url(url: str) -> str:
    """Normalize a job URL enough for within-run deduplication."""

    parsed = urlparse(url or "")
    query = parse_qs(parsed.query)
    for key in ("trk", "refId", "trackingId", "position", "pageNum"):
        query.pop(key, None)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def job_from_record(record: JobRecord | Mapping[str, Any], *, search_url: str = "") -> JobRecord:
    """Convert a mapping or JobRecord into the stable JobRecord shape."""

    if isinstance(record, JobRecord):
        if search_url and not record.search_url:
            return JobRecord(**{**record.__dict__, "search_url": search_url})
        return record

    raw = dict(record)
    job_id = normalize_space(raw.get("job_id") or raw.get("linkedin_job_id") or raw.get("id") or "")
    url = normalize_space(raw.get("url") or raw.get("linkedin_url") or "")
    return JobRecord(
        job_id=job_id,
        title=normalize_space(raw.get("title") or raw.get("role") or ""),
        company=normalize_space(raw.get("company") or ""),
        url=url,
        location=normalize_space(raw.get("location") or ""),
        source=normalize_space(raw.get("source") or "linkedin"),
        search_url=normalize_space(raw.get("search_url") or search_url),
        ats=normalize_space(raw.get("ats") or ""),
        raw=raw,
    )


def dedupe_jobs(
    records: Sequence[JobRecord | Mapping[str, Any]], *, search_url: str
) -> list[JobRecord]:
    """Deduplicate by LinkedIn job id first, then normalized URL fallback."""

    seen: set[str] = set()
    jobs: list[JobRecord] = []
    for record in records:
        job = job_from_record(record, search_url=search_url)
        dedupe_key = f"id:{job.job_id}" if job.job_id else f"url:{normalized_job_url(job.url)}"
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        jobs.append(job)
    return jobs


def _job_payload(job: JobRecord) -> dict[str, Any]:
    url = normalize_url_for_audit(job.url)
    search_url = normalize_url_for_audit(job.search_url)
    return {
        "job_id": job.job_id,
        "title": job.title,
        "company": job.company,
        "url": url,
        "domain": domain_from_url(url),
        "location": job.location,
        "source": job.source,
        "search_url": search_url,
        "ats": job.ats,
    }


def _report_artifacts(artifacts: Sequence[ReportArtifact] | None) -> list[ReportArtifact]:
    return list(artifacts or [])


def run_search_workflow(
    request: SearchRequest,
    discovery: LinkedInDiscovery,
    report_sink: ReportSink,
    submission_policy: SubmissionPolicy | None = None,
) -> SearchResult:
    """Run search-only discovery, deduplication, and reporting."""

    search_url = build_search_url(request)
    effective_limit = clamp_search_limit(request.limit)
    records: Sequence[JobRecord | Mapping[str, Any]] = []
    if effective_limit > 0:
        records = discovery.discover(
            SearchRequest(
                limit=effective_limit,
                search_url=search_url,
                query=request.query,
                location=request.location,
                profile=dict(request.profile),
                paths=request.paths,
            )
        )

    jobs = dedupe_jobs(records, search_url=search_url)[:effective_limit]
    timestamp = utc_timestamp()
    events = [
        {
            "type": "job",
            "action": "discovered",
            "status": "recorded",
            "surface": "linkedin_search",
            "ats": job.ats,
            "blocked_reason": "",
            "unknown_questions": [],
            "required_empty_count": 0,
            **_job_payload(job),
        }
        for job in jobs
    ]
    summary = {
        "command": "search",
        "requested_limit": request.limit,
        "effective_limit": effective_limit,
        "discovered": len(records),
        "deduplicated": len(jobs),
        "submitted": 0,
    }
    report = {
        "command": "search",
        "timestamp": timestamp,
        "search_url": search_url,
        "jobs": [_job_payload(job) for job in jobs],
        "events": events,
        "summary": summary,
    }
    artifacts = _report_artifacts(report_sink.write("search", report))
    return SearchResult(
        timestamp=timestamp,
        search_url=search_url,
        jobs=jobs,
        events=events,
        summary=summary,
        reports=artifacts,
    )


def surface_identity_from_detection(detection: DetectionResult) -> SurfaceIdentity:
    """Build a stable fill-once identity for a detected surface."""

    page = detection.page
    url = normalize_space(getattr(page, "url", "") if page is not None else "")
    title_attr = getattr(page, "title", "")
    title = title_attr() if callable(title_attr) else title_attr
    context = dict(detection.job_context or {})
    return SurfaceIdentity(
        url=url or normalize_space(context.get("apply_url") or context.get("url") or ""),
        title=normalize_space(title or context.get("title") or context.get("role") or ""),
        surface=normalize_space(detection.surface),
        ats=normalize_space(detection.ats),
        job_id=normalize_space(context.get("job_id") or ""),
    )


def _assist_event(
    event_type: str,
    detection: DetectionResult,
    result: FillResult,
    identity: SurfaceIdentity,
    *,
    status: str,
    blocked_reason: str = "",
) -> AssistEvent:
    return AssistEvent(
        type=event_type,
        surface=detection.surface,
        ats=detection.ats,
        status=status,
        filled_count=len(result.filled),
        required_empty_count=len(result.required_empty),
        unknown_count=len(result.unknown_questions),
        reached_submit_step=bool(result.reached_submit_step),
        blocked_reason=blocked_reason,
        job=dict(detection.job_context or {}),
        identity=identity,
        required_empty=list(result.required_empty),
        unknown_questions=list(result.unknown_questions),
        timestamp=utc_timestamp(),
    )


def _event_payload(event: AssistEvent) -> dict[str, Any]:
    job = _bounded_job_context(event.job)
    identity = _identity_payload(event.identity)
    return {
        "type": event.type,
        "action": event.type,
        "timestamp": event.timestamp,
        "surface": event.surface,
        "ats": event.ats,
        "status": event.status,
        "filled_count": event.filled_count,
        "required_empty_count": event.required_empty_count,
        "unknown_count": event.unknown_count,
        "reached_submit_step": event.reached_submit_step,
        "blocked_reason": event.blocked_reason,
        "job": job,
        "identity": identity,
        "required_empty": list(event.required_empty),
        "unknown_questions": [_unknown_question_payload(item) for item in event.unknown_questions],
        "feedback": compact_assist_feedback(event),
    }


def _bounded_job_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    ctx = dict(context or {})
    url = normalize_url_for_audit(ctx.get("apply_url") or ctx.get("url") or "")
    domain = domain_from_url(url or ctx.get("domain") or "")
    return {
        "job_id": normalize_space(ctx.get("job_id") or ""),
        "company": normalize_space(ctx.get("company") or ""),
        "role": normalize_space(ctx.get("role") or ctx.get("title") or ""),
        "title": normalize_space(ctx.get("title") or ctx.get("role") or ""),
        "url": url,
        "domain": domain,
        "ats": normalize_space(ctx.get("ats") or ""),
    }


def _identity_payload(identity: SurfaceIdentity | None) -> dict[str, Any]:
    if identity is None:
        return {}
    url = normalize_url_for_audit(identity.url)
    return {
        "url": url,
        "domain": domain_from_url(url),
        "title": identity.title,
        "surface": identity.surface,
        "ats": identity.ats,
        "job_id": identity.job_id,
    }


def _unknown_question_payload(item: Any) -> dict[str, Any] | str:
    if not isinstance(item, Mapping):
        return normalize_space(item)
    url = normalize_url_for_audit(item.get("apply_url") or item.get("url") or "")
    return {
        "question": normalize_space(item.get("question") or ""),
        "field_type": normalize_space(item.get("field_type") or "text"),
        "required": bool(item.get("required")),
        "ats": normalize_space(item.get("ats") or ""),
        "company": normalize_space(item.get("company") or ""),
        "role": normalize_space(item.get("role") or item.get("title") or ""),
        "domain": domain_from_url(url or item.get("domain") or ""),
    }


def compact_assist_feedback(event: AssistEvent) -> str:
    """Return one compact user-facing assist feedback line."""

    surface = event.surface or "none"
    ats = event.ats or "unknown"
    return (
        f"{surface}/{ats} status={event.status or 'unknown'} "
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
    """Run one bounded assistive fill-only session."""

    session: BrowserSession | None = None
    events: list[AssistEvent] = []
    seen: set[str] = set()
    timestamp = utc_timestamp()
    try:
        session = session_factory.open(request)
        if request.start_url:
            session.open_url(request.start_url)

        cycles = clamp_assist_cycles(request.max_cycles)
        for _ in range(cycles):
            detection = detector.detect(session)
            if detection.surface == "none":
                continue
            identity = surface_identity_from_detection(detection)
            if detection.surface == "browser_blocked":
                blocked_reason = normalize_space(
                    detection.job_context.get("blocked_reason")
                    or "Visible browser requires user action."
                )
                events.append(
                    _assist_event(
                        "blocked",
                        detection,
                        FillResult(surface=detection.surface),
                        identity,
                        status="blocked",
                        blocked_reason=blocked_reason,
                    )
                )
                continue
            if identity.key() in seen:
                events.append(
                    AssistEvent(
                        type="skipped",
                        surface=detection.surface,
                        ats=detection.ats,
                        status="duplicate",
                        job=dict(detection.job_context or {}),
                        identity=identity,
                        timestamp=utc_timestamp(),
                    )
                )
                continue
            seen.add(identity.key())
            fill_surface = getattr(fill_adapter, "fill")
            fill_result = fill_surface(
                detection,
                dict(request.profile),
                bank,
                dict(request.qa_context),
                dict(request.documents),
            )
            status = "blocked" if fill_result.required_empty else "filled"
            blocked_reason = "; ".join(str(item) for item in fill_result.required_empty)
            events.append(
                _assist_event(
                    "filled",
                    detection,
                    fill_result,
                    identity,
                    status=status,
                    blocked_reason=blocked_reason,
                )
            )
    finally:
        # Live sessions are intentionally visible; factories can choose no-op close.
        if session is not None and getattr(session, "close_on_exit", False):
            session.close()

    summary = {
        "command": "assist",
        "mode": request.mode,
        "requested_cycles": request.max_cycles,
        "effective_cycles": clamp_assist_cycles(request.max_cycles),
        "events": len(events),
        "filled": sum(1 for event in events if event.type == "filled"),
        "blocked": sum(1 for event in events if event.status == "blocked"),
        "duplicates": sum(1 for event in events if event.status == "duplicate"),
        "required_empty": sum(event.required_empty_count for event in events),
        "unknown_questions": sum(event.unknown_count for event in events),
        "submitted": 0,
    }
    report = {
        "command": "assist",
        "timestamp": timestamp,
        "events": [_event_payload(event) for event in events],
        "summary": summary,
    }
    artifacts = _report_artifacts(report_sink.write("assist", report))
    return AssistResult(timestamp=timestamp, events=events, summary=summary, reports=artifacts)
