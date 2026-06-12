from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from linkedin_apply_assistant.contracts import AssistRequest, JobRecord, SearchRequest
from linkedin_apply_assistant.form_engine import DetectionResult, FillResult
from linkedin_apply_assistant.workflows import run_assist_workflow, run_search_workflow


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"
WORKFLOWS = SRC_DIR / "linkedin_apply_assistant" / "workflows.py"


class FakeDiscovery:
    def discover(self, request: SearchRequest) -> list[JobRecord]:
        return [
            JobRecord(
                job_id="123",
                title="Engineer",
                company="Example",
                url="https://www.linkedin.com/jobs/view/123/",
            )
        ]


class FakeReportSink:
    def __init__(self) -> None:
        self.reports: list[dict[str, Any]] = []

    def write(self, command: str, report: dict[str, Any]) -> list[Any]:
        self.reports.append({"command": command, "report": report})
        return []


class FakeSession:
    close_on_exit = False

    @property
    def pages(self) -> list[Any]:
        return []

    def open_url(self, url: str) -> None:
        self.opened_url = url

    def close(self) -> None:
        self.closed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def open(self, request: AssistRequest) -> FakeSession:
        return self.session


class FakeDetector:
    def detect(self, session: FakeSession) -> DetectionResult:
        return DetectionResult(
            surface="external_ats",
            page=type("Page", (), {"url": "https://jobs.example.test/apply", "title": "Role"})(),
            ats="greenhouse",
            job_context={"job_id": "123", "company": "Example", "role": "Engineer"},
        )


class FakeFillAdapter:
    def __init__(self) -> None:
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
        return FillResult(filled=["email"], surface=detection.surface)


class FakeSubmissionPolicy:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, action: str, context: dict[str, Any] | None = None) -> Any:
        self.calls += 1
        return None


def test_search_workflow_uses_fake_discovery_and_report_sink() -> None:
    sink = FakeReportSink()
    policy = FakeSubmissionPolicy()

    result = run_search_workflow(
        SearchRequest(limit=1, search_url="https://www.linkedin.com/jobs/search/?currentJobId=123"),
        FakeDiscovery(),
        sink,
        policy,
    )

    assert len(result.jobs) == 1
    assert result.summary["submitted"] == 0
    assert sink.reports[0]["command"] == "search"
    assert policy.calls == 0


def test_assist_workflow_uses_fake_boundaries_and_does_not_submit() -> None:
    sink = FakeReportSink()
    policy = FakeSubmissionPolicy()
    fill = FakeFillAdapter()

    result = run_assist_workflow(
        AssistRequest(max_cycles=1, profile={"email": "person@example.test"}),
        FakeSessionFactory(),
        FakeDetector(),
        fill,
        sink,
        policy,
    )

    assert fill.calls == 1
    assert result.summary["filled"] == 1
    assert result.summary["submitted"] == 0
    assert policy.calls == 0
    assert sink.reports[0]["command"] == "assist"


def test_workflows_module_is_selector_light() -> None:
    text = WORKFLOWS.read_text(encoding="utf-8")
    blocked = ("locator(", ".fill(", ".click(", "button[", "input[", "textarea", "select[")

    for term in blocked:
        assert term not in text


def test_workflow_imports_have_no_cwd_side_effects(tmp_path: Path) -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import linkedin_apply_assistant.contracts; import linkedin_apply_assistant.workflows; print('ok')",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "data").exists()
