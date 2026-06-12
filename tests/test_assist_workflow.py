from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
import sys
import types
from typing import Any

from linkedin_apply_assistant import cli
from linkedin_apply_assistant.apply_reports import RuntimeReportSink
from linkedin_apply_assistant.browser_sessions import (
    VisibleBrowserSession,
    VisibleBrowserSessionFactory,
    page_auth_status,
)
from linkedin_apply_assistant.contracts import AssistRequest
from linkedin_apply_assistant.form_engine import DetectionResult, FillResult
from linkedin_apply_assistant.linkedin_layer import (
    CurrentSurfaceDetector,
    CurrentSurfaceFillAdapter,
    detect_current_apply_surface,
)
from linkedin_apply_assistant.paths import resolve_runtime_paths
from linkedin_apply_assistant.safety import BROWSER_PROFILE_WARNING
from linkedin_apply_assistant.workflows import (
    compact_assist_feedback,
    run_assist_workflow,
    surface_identity_from_detection,
)


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://jobs.lever.co/example/1",
        title: str = "Example Engineer",
        surface: str = "",
        has_form: bool = True,
        company: str = "Example",
        role: str = "Engineer",
        job_id: str = "job-1",
        auth_status: str = "",
    ) -> None:
        self.url = url
        self._title = title
        self.surface = surface
        self.has_form = has_form
        self.company = company
        self.role = role
        self.job_id = job_id
        self.auth_status = auth_status
        self.filled: list[tuple[tuple[str, ...], str]] = []
        self.submit_calls = 0

    def title(self) -> str:
        return self._title

    def fill_field(self, selectors: tuple[str, ...], value: str) -> bool:
        self.filled.append((selectors, value))
        return True

    def submit(self) -> None:
        self.submit_calls += 1


class FakeSession:
    close_on_exit = False

    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages
        self.opened: list[str] = []
        self.closed = False

    def open_url(self, url: str) -> None:
        self.opened.append(url)

    def close(self) -> None:
        self.closed = True


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.calls = 0

    def open(self, request: AssistRequest) -> FakeSession:
        self.calls += 1
        return self.session


class SequenceDetector:
    def __init__(self, detections: list[DetectionResult]) -> None:
        self.detections = detections
        self.calls = 0

    def detect(self, session: FakeSession) -> DetectionResult:
        self.calls += 1
        index = min(self.calls - 1, len(self.detections) - 1)
        return self.detections[index]


class FakeFillAdapter:
    def __init__(self, result: FillResult) -> None:
        self.result = result
        self.calls = 0

    def fill(
        self,
        detection: DetectionResult,
        profile: dict[str, Any],
        bank: Any = None,
        qa_context: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
    ) -> FillResult:
        self.calls += 1
        return self.result


class CapturingSink:
    def __init__(self) -> None:
        self.reports: list[dict[str, Any]] = []

    def write(self, command: str, report: dict[str, Any]) -> list[Any]:
        self.reports.append({"command": command, "report": report})
        return []


class CountingPolicy:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, action: str, context: dict[str, Any] | None = None) -> Any:
        self.calls += 1
        return None


def _external_detection(page: FakePage | None = None) -> DetectionResult:
    page = page or FakePage()
    return DetectionResult(
        surface="external_ats",
        page=page,
        ats="lever",
        job_context={
            "company": "Example",
            "role": "Engineer",
            "apply_url": page.url,
            "job_id": "job-1",
            "ats": "lever",
        },
    )


def test_detect_current_surface_prefers_newest_page_and_carries_context() -> None:
    older = FakePage(url="https://boards.greenhouse.io/example/jobs/1", company="Old")
    newer = FakePage(
        url="https://unknown.example.test/apply",
        company="New",
        role="Staff Engineer",
        job_id="job-2",
    )
    session = FakeSession([older, newer])

    detection = detect_current_apply_surface(session)

    assert detection.surface == "external_ats"
    assert detection.ats == "generic"
    assert detection.job_context["company"] == "New"
    assert detection.job_context["role"] == "Staff Engineer"
    assert detection.job_context["job_id"] == "job-2"


def test_surface_identity_uses_stable_page_fields_without_dom_hash() -> None:
    page = FakePage(url="https://jobs.lever.co/example/1?utm=x", title="Role")
    detection = _external_detection(page)

    identity = surface_identity_from_detection(detection)

    assert identity.url == page.url
    assert identity.title == "Role"
    assert identity.surface == "external_ats"
    assert identity.ats == "lever"
    assert identity.job_id == "job-1"
    assert "hash" not in identity.key().lower()


def test_assist_workflow_fills_each_surface_identity_once() -> None:
    page = FakePage()
    detection = _external_detection(page)
    session = FakeSession([page])
    factory = FakeSessionFactory(session)
    detector = SequenceDetector([detection, detection])
    fill_adapter = FakeFillAdapter(FillResult(filled=["email"], surface="external:lever"))
    sink = CapturingSink()
    policy = CountingPolicy()

    result = run_assist_workflow(
        AssistRequest(max_cycles=2, profile={"email": "ada@example.test"}),
        factory,
        detector,
        fill_adapter,
        sink,
        policy,
    )

    assert factory.calls == 1
    assert fill_adapter.calls == 1
    assert policy.calls == 0
    assert result.summary["filled"] == 1
    assert result.summary["duplicates"] == 1
    assert [event.status for event in result.events] == ["filled", "duplicate"]
    assert sink.reports[0]["report"]["events"][0]["feedback"]
    assert page.submit_calls == 0


def test_assist_workflow_fills_distinct_external_and_easy_apply_surfaces_once_each() -> None:
    external = FakePage(url="https://jobs.lever.co/example/1", title="External")
    easy = FakePage(
        url="https://www.linkedin.com/jobs/view/2",
        title="Easy",
        surface="linkedin_easy_apply",
        job_id="job-2",
    )
    detections = [
        _external_detection(external),
        DetectionResult(
            surface="linkedin_easy_apply",
            page=easy,
            ats="linkedin",
            job_context={
                "company": "Example",
                "role": "Engineer",
                "apply_url": easy.url,
                "job_id": "job-2",
            },
        ),
    ]
    fill_adapter = FakeFillAdapter(FillResult(filled=["email"], surface="filled"))

    result = run_assist_workflow(
        AssistRequest(max_cycles=2),
        FakeSessionFactory(FakeSession([external, easy])),
        SequenceDetector(detections),
        fill_adapter,
        CapturingSink(),
    )

    assert fill_adapter.calls == 2
    assert result.summary["filled"] == 2
    assert result.summary["duplicates"] == 0
    assert external.submit_calls == 0
    assert easy.submit_calls == 0


def test_assist_workflow_reports_blockers_and_unknowns(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)
    detection = _external_detection()
    fill_result = FillResult(
        filled=["email", "phone"],
        required_empty=["resume document path is required but not configured."],
        unknown_questions=[{"question": "Expected salary?", "required": True}],
        reached_submit_step=True,
        surface="external:lever",
    )

    result = run_assist_workflow(
        AssistRequest(max_cycles=1, profile={"email": "ada@example.test"}, paths=paths),
        FakeSessionFactory(FakeSession([detection.page])),
        SequenceDetector([detection]),
        FakeFillAdapter(fill_result),
        RuntimeReportSink(paths=paths),
    )

    assert result.summary["blocked"] == 1
    assert result.summary["submitted"] == 0
    assert compact_assist_feedback(result.events[0]).endswith("submit_step=true")
    json_report = next(artifact.path for artifact in result.reports if artifact.kind == "json")
    payload = json.loads(json_report.read_text(encoding="utf-8"))
    event = payload["events"][0]
    assert event["action"] == "filled"
    assert event["status"] == "blocked"
    assert event["required_empty_count"] == 1
    assert event["unknown_count"] == 1
    assert event["blocked_reason"]


def test_assist_report_preserves_bare_domain_when_url_is_missing() -> None:
    page = FakePage(url="")
    detection = DetectionResult(
        surface="external_ats",
        page=page,
        ats="lever",
        job_context={
            "company": "Example",
            "role": "Engineer",
            "domain": "jobs.example.test",
            "ats": "lever",
        },
    )
    sink = CapturingSink()

    run_assist_workflow(
        AssistRequest(max_cycles=1),
        FakeSessionFactory(FakeSession([page])),
        SequenceDetector([detection]),
        FakeFillAdapter(
            FillResult(
                filled=["email"],
                unknown_questions=[
                    {
                        "question": "Expected salary?",
                        "field_type": "text",
                        "domain": "jobs.example.test",
                    }
                ],
                surface="external:lever",
            )
        ),
        sink,
    )

    event = sink.reports[0]["report"]["events"][0]
    assert event["job"]["domain"] == "jobs.example.test"
    assert event["unknown_questions"][0]["domain"] == "jobs.example.test"


def test_assist_workflow_blocks_login_pages_without_filling() -> None:
    page = FakePage(url="https://www.linkedin.com/login", auth_status="login")
    session = FakeSession([page])
    detector = CurrentSurfaceDetector()
    fill_adapter = CurrentSurfaceFillAdapter()

    result = run_assist_workflow(
        AssistRequest(max_cycles=1),
        FakeSessionFactory(session),
        detector,
        fill_adapter,
        CapturingSink(),
    )

    assert page_auth_status(page) == "login"
    assert result.summary["blocked"] == 1
    assert result.events[0].type == "blocked"
    assert "visible browser" in result.events[0].blocked_reason
    assert page.filled == []
    assert page.submit_calls == 0


def test_assist_workflow_opens_start_url_and_keeps_visible_session_open() -> None:
    page = FakePage()
    session = FakeSession([page])

    result = run_assist_workflow(
        AssistRequest(start_url="https://www.linkedin.com/jobs/search/", max_cycles=0),
        FakeSessionFactory(session),
        SequenceDetector([_external_detection(page)]),
        FakeFillAdapter(FillResult()),
        CapturingSink(),
    )

    assert result.summary["events"] == 0
    assert session.opened == ["https://www.linkedin.com/jobs/search/"]
    assert session.closed is False


def test_assist_workflow_clamps_over_cap_cycles_without_filling() -> None:
    page = FakePage()
    detector = SequenceDetector([DetectionResult(surface="none", page=page)])

    result = run_assist_workflow(
        AssistRequest(max_cycles=100),
        FakeSessionFactory(FakeSession([page])),
        detector,
        FakeFillAdapter(FillResult(filled=["email"])),
        CapturingSink(),
    )

    assert detector.calls == 25
    assert result.summary["requested_cycles"] == 100
    assert result.summary["effective_cycles"] == 25
    assert result.summary["events"] == 0


def test_visible_browser_session_stops_manager_when_context_close_fails() -> None:
    class RaisingContext:
        def close(self) -> None:
            raise RuntimeError("close failed")

    class Manager:
        def __init__(self) -> None:
            self.stopped = False

        def stop(self) -> None:
            self.stopped = True

    manager = Manager()
    session = VisibleBrowserSession(context=RaisingContext())
    setattr(session, "_playwright_manager", manager)

    try:
        session.close()
    except RuntimeError as exc:
        assert str(exc) == "close failed"
    else:
        raise AssertionError("expected close failure")

    assert manager.stopped is True


def test_visible_browser_factory_stops_manager_when_launch_fails(
    monkeypatch: Any, tmp_path: Path
) -> None:
    class Chromium:
        def launch_persistent_context(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("launch failed")

    class Manager:
        def __init__(self) -> None:
            self.chromium = Chromium()
            self.stopped = False

        def stop(self) -> None:
            self.stopped = True

    class Starter:
        def __init__(self, manager: Manager) -> None:
            self.manager = manager

        def start(self) -> Manager:
            return self.manager

    manager = Manager()
    playwright_module = types.ModuleType("playwright")
    sync_api_module = types.ModuleType("playwright.sync_api")
    sync_api_module.sync_playwright = lambda: Starter(manager)
    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

    factory = VisibleBrowserSessionFactory(resolve_runtime_paths(workspace=tmp_path))

    try:
        factory.open(AssistRequest())
    except RuntimeError as exc:
        message = str(exc)
        assert "Browser setup failed: Chromium could not be launched." in message
        assert "Try: python -m playwright install chromium" in message
        assert "Browser profile:" in message
    else:
        raise AssertionError("expected launch failure")

    assert manager.stopped is True


def test_cli_assist_handler_delegates_to_workflow_without_placeholder_wording(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    calls: dict[str, Any] = {}

    class FakeFactory:
        def __init__(self, paths: Any) -> None:
            calls["browser_profile_dir"] = paths.browser_profile_dir

    def fake_workflow(
        request: AssistRequest,
        session_factory: Any,
        detector: Any,
        fill_adapter: Any,
        report_sink: Any,
        submission_policy: Any = None,
        bank: Any = None,
    ) -> Any:
        calls["request"] = request
        return type(
            "Result",
            (),
            {
                "events": [],
                "summary": {
                    "mode": request.mode,
                    "events": 0,
                    "filled": 0,
                    "blocked": 0,
                    "submitted": 0,
                },
                "reports": [],
            },
        )()

    monkeypatch.setattr(cli, "VisibleBrowserSessionFactory", FakeFactory)
    monkeypatch.setattr(cli, "run_assist_workflow", fake_workflow)

    code = cli._handle_assist(
        Namespace(
            workspace=str(tmp_path),
            config=None,
            qa_bank=None,
            browser_profile=None,
            output_dir=None,
            verbose=True,
            start_url=None,
            mode="auto-watch",
            max_cycles=0,
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert BROWSER_PROFILE_WARNING in output
    assert "Assist complete." in output
    assert "de" + "ferred" not in output.lower()
    assert calls["request"].mode == "auto-watch"
    assert calls["request"].max_cycles == 0
    assert calls["browser_profile_dir"] == tmp_path / "browser-profile"
