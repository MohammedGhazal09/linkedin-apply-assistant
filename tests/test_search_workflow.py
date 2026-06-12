from __future__ import annotations

import json
from typing import Any

from linkedin_apply_assistant.apply_reports import RuntimeReportSink
from linkedin_apply_assistant.contracts import SearchRequest
from linkedin_apply_assistant.linkedin_layer import BrowserLinkedInDiscovery
from linkedin_apply_assistant.paths import resolve_runtime_paths
from linkedin_apply_assistant.workflows import (
    build_search_url,
    dedupe_jobs,
    run_search_workflow,
)


class FakeDiscovery:
    def __init__(self) -> None:
        self.calls = 0
        self.last_limit: int | None = None

    def discover(self, request: SearchRequest) -> list[dict[str, Any]]:
        self.calls += 1
        self.last_limit = request.limit
        return [
            {
                "job_id": "100",
                "title": "Engineer",
                "company": "Example",
                "url": "https://www.linkedin.com/jobs/view/100/",
                "location": "Remote",
            },
            {
                "job_id": "100",
                "title": "Engineer duplicate",
                "company": "Example",
                "url": "https://www.linkedin.com/jobs/view/100/?trk=dup",
            },
            {
                "title": "Fallback URL",
                "company": "Example",
                "url": "https://jobs.example.test/apply?trk=abc",
            },
            {
                "title": "Fallback URL duplicate",
                "company": "Example",
                "url": "https://jobs.example.test/apply?trk=def",
            },
        ]


class CountingPolicy:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, action: str, context: dict[str, Any] | None = None) -> Any:
        self.calls += 1
        return None


def test_search_url_prefers_sanitized_search_url() -> None:
    request = SearchRequest(
        search_url="https://www.linkedin.com/jobs/search/?keywords=python&currentJobId=123&start=25",
        query="ignored",
        location="ignored",
    )

    assert build_search_url(request) == "https://www.linkedin.com/jobs/search/?keywords=python"


def test_search_url_builds_from_query_and_location() -> None:
    request = SearchRequest(query="python engineer", location="Riyadh")

    url = build_search_url(request)

    assert url.startswith("https://www.linkedin.com/jobs/search/")
    assert "keywords=python+engineer" in url
    assert "location=Riyadh" in url


def test_dedup_prefers_job_id_then_normalized_url() -> None:
    jobs = dedupe_jobs(FakeDiscovery().discover(SearchRequest()), search_url="https://search")

    assert [job.title for job in jobs] == ["Engineer", "Fallback URL"]


def test_search_workflow_writes_structured_reports(tmp_path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)
    discovery = FakeDiscovery()
    policy = CountingPolicy()

    result = run_search_workflow(
        SearchRequest(
            limit=10,
            search_url="https://www.linkedin.com/jobs/search/?keywords=python",
            paths=paths,
        ),
        discovery,
        RuntimeReportSink(paths=paths),
        policy,
    )

    assert discovery.calls == 1
    assert policy.calls == 0
    assert result.summary["deduplicated"] == 2
    assert len(result.reports) == 2
    json_report = next(artifact.path for artifact in result.reports if artifact.kind == "json")
    payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert payload["command"] == "search"
    assert payload["summary"]["submitted"] == 0
    assert payload["summary"]["effective_limit"] == 10
    assert payload["jobs"][0]["job_id"] == "100"
    assert payload["jobs"][0]["domain"] == "www.linkedin.com"
    assert payload["jobs"][1]["url"] == "https://jobs.example.test/apply"
    assert payload["jobs"][1]["domain"] == "jobs.example.test"
    assert {
        "surface",
        "ats",
        "blocked_reason",
        "unknown_questions",
        "required_empty_count",
    }.issubset(payload["events"][0])
    assert str(tmp_path) in str(json_report)


def test_limit_zero_search_does_not_call_discovery(tmp_path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)
    discovery = FakeDiscovery()

    result = run_search_workflow(
        SearchRequest(limit=0, query="python", paths=paths),
        discovery,
        RuntimeReportSink(paths=paths),
    )

    assert discovery.calls == 0
    assert result.jobs == []
    assert result.summary["submitted"] == 0
    assert result.summary["effective_limit"] == 0


def test_over_cap_search_limit_is_clamped_before_discovery(tmp_path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)
    discovery = FakeDiscovery()

    result = run_search_workflow(
        SearchRequest(limit=100, query="python", paths=paths),
        discovery,
        RuntimeReportSink(paths=paths),
    )

    assert discovery.calls == 1
    assert discovery.last_limit == 25
    assert result.summary["requested_limit"] == 100
    assert result.summary["effective_limit"] == 25


def test_browser_linkedin_discovery_closes_owned_session_on_failure() -> None:
    class Session:
        close_on_exit = True

        def __init__(self) -> None:
            self.pages: list[Any] = []
            self.closed = False

        def open_url(self, url: str) -> None:
            raise RuntimeError("navigation failed")

        def close(self) -> None:
            self.closed = True

    class Factory:
        def __init__(self, session: Session) -> None:
            self.session = session

        def open(self, request: SearchRequest) -> Session:
            return self.session

    session = Session()
    discovery = BrowserLinkedInDiscovery(Factory(session))

    try:
        discovery.discover(SearchRequest(search_url="https://www.linkedin.com/jobs/search/"))
    except RuntimeError as exc:
        assert str(exc) == "navigation failed"
    else:
        raise AssertionError("expected navigation failure")

    assert session.closed is True
