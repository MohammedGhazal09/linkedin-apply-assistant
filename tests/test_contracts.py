from __future__ import annotations

from pathlib import Path

from linkedin_apply_assistant.contracts import (
    AssistEvent,
    AssistRequest,
    AssistResult,
    JobRecord,
    ReportArtifact,
    SearchRequest,
    SearchResult,
    SubmitDecision,
    SubmissionResult,
    SurfaceIdentity,
)


def test_contract_dataclasses_are_plain_values() -> None:
    request = SearchRequest(limit=0, query="python", location="remote")
    job = JobRecord(
        job_id="123",
        title="Engineer",
        company="Example",
        url="https://www.linkedin.com/jobs/view/123/",
    )
    search_result = SearchResult(
        timestamp="2026-06-07T00:00:00+00:00",
        search_url="https://www.linkedin.com/jobs/search/",
        jobs=[job],
        summary={"submitted": 0},
        reports=[ReportArtifact(kind="json", path=Path("report.json"))],
    )

    assert request.limit == 0
    assert search_result.jobs[0].job_id == "123"
    assert search_result.reports[0].kind == "json"


def test_assist_and_submission_contract_shapes() -> None:
    identity = SurfaceIdentity(
        url="https://jobs.example.test/apply",
        title="Engineer",
        surface="external_ats",
        ats="greenhouse",
        job_id="123",
    )
    event = AssistEvent(
        type="filled",
        surface="external_ats",
        ats="greenhouse",
        status="filled",
        filled_count=2,
        identity=identity,
    )
    result = AssistResult(
        timestamp="2026-06-07T00:00:00+00:00",
        events=[event],
        summary={"submitted": 0},
    )
    request = AssistRequest(mode="auto", max_cycles=1)
    decision = SubmissionResult(status="disabled", reason="blocked", allowed=False)
    audit = SubmitDecision(command="apply", action="submit", allowed=False, status="disabled")

    assert request.mode == "auto"
    assert result.events[0].identity is not None
    assert result.events[0].identity.key().count("|") == 4
    assert decision.allowed is False
    assert audit.command == "apply"
