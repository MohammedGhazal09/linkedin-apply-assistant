"""Package-local report writers for standalone runtime paths."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .contracts import ReportArtifact
from .paths import RuntimePaths
from .redaction import sanitize_markdown_value, sanitize_report_payload


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")


def _safe_filename_prefix(filename_prefix: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(filename_prefix or "")).strip(".-")
    return safe or "report"


def _report_filename(filename_prefix: str, extension: str, *, timestamp: str | None = None) -> str:
    report_timestamp = timestamp or _timestamp()
    return (
        f"{_safe_filename_prefix(filename_prefix)}_{report_timestamp}_{uuid4().hex[:8]}.{extension}"
    )


def _esc(value: Any) -> str:
    return sanitize_markdown_value(value)


def _event_context_label(event: dict[str, Any]) -> str:
    job = event.get("job")
    if not isinstance(job, dict):
        job = {}
    company = event.get("company") or job.get("company") or ""
    role = event.get("role") or event.get("title") or job.get("role") or job.get("title") or ""
    return f"{_esc(company)} {_esc(role)}".strip()


def resolve_reports_dir(
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> Path:
    """Resolve the report directory from explicit input or runtime paths."""

    if reports_dir is not None:
        return Path(reports_dir).expanduser()
    if paths is not None:
        return paths.reports_dir
    raise ValueError("reports_dir or paths is required")


def write_json_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
    filename_prefix: str = "report",
) -> Path:
    """Write a JSON report under an explicit standalone report directory."""

    target_dir = resolve_reports_dir(paths=paths, reports_dir=reports_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _report_filename(filename_prefix, "json")
    sanitized = sanitize_report_payload(report)
    target.write_text(
        json.dumps(sanitized, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return target


def write_markdown_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
    filename_prefix: str = "report",
) -> Path:
    """Write a compact Markdown report under an explicit standalone directory."""

    target_dir = resolve_reports_dir(paths=paths, reports_dir=reports_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    report_timestamp = _timestamp()
    target = target_dir / _report_filename(filename_prefix, "md", timestamp=report_timestamp)
    sanitized = sanitize_report_payload(report)
    summary = sanitized.get("summary", {}) if isinstance(sanitized, dict) else {}
    events = sanitized.get("events", []) if isinstance(sanitized, dict) else []
    lines = [
        f"# LinkedIn-apply-assistant Report - {report_timestamp}",
        "",
    ]
    if isinstance(summary, dict):
        lines.append("## Summary")
        lines.append("")
        for key in sorted(summary):
            lines.append(f"- **{_esc(key)}:** {_esc(summary[key])}")
        lines.append("")
    if isinstance(events, list):
        lines.append("## Events")
        lines.append("")
        for event in events:
            if isinstance(event, dict):
                label = event.get("type", "event")
                context_label = _event_context_label(event)
                details = []
                for key in (
                    "status",
                    "surface",
                    "ats",
                    "blocked_reason",
                    "filled_count",
                    "required_empty_count",
                    "unknown_count",
                    "domain",
                ):
                    value = event.get(key)
                    if value not in (None, "", [], {}):
                        details.append(f"{_esc(key)}={_esc(value)}")
                suffix = f" - {'; '.join(details)}" if details else ""
                lines.append(f"- **{_esc(label)}** {context_label}{suffix}".rstrip())
        lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def write_dry_run_report(jobs: list[dict[str, Any]], report_path: str | Path) -> Path:
    """Write a dry-run JSON report to an explicit file path."""

    target = Path(report_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    passed = [job for job in jobs if job.get("pass")]
    payload = {
        "timestamp": _timestamp(),
        "total": len(jobs),
        "passed": len(passed),
        "results": jobs,
    }
    safe_payload = sanitize_report_payload(payload)
    target.write_text(json.dumps(safe_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def write_assistive_session_report(
    report: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write JSON and Markdown reports for a local assistive session."""

    prefix = "assistive-session"
    payload = dict(report)
    _ = profile
    json_path = write_json_report(
        payload,
        paths=paths,
        reports_dir=reports_dir,
        filename_prefix=prefix,
    )
    md_path = write_markdown_report(
        payload,
        paths=paths,
        reports_dir=reports_dir,
        filename_prefix=prefix,
    )
    return json_path, md_path


def write_search_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write JSON and Markdown reports for a search workflow."""

    json_path = write_json_report(
        report,
        paths=paths,
        reports_dir=reports_dir,
        filename_prefix="search",
    )
    md_path = write_markdown_report(
        report,
        paths=paths,
        reports_dir=reports_dir,
        filename_prefix="search",
    )
    return json_path, md_path


class RuntimeReportSink:
    """ReportSink implementation backed by explicit runtime paths."""

    def __init__(
        self,
        *,
        paths: RuntimePaths | None = None,
        reports_dir: str | Path | None = None,
    ) -> None:
        self.paths = paths
        self.reports_dir = reports_dir

    def write(self, command: str, report: dict[str, Any]) -> list[ReportArtifact]:
        prefix = "assistive-session" if command == "assist" else command
        json_path = write_json_report(
            report,
            paths=self.paths,
            reports_dir=self.reports_dir,
            filename_prefix=prefix,
        )
        md_path = write_markdown_report(
            report,
            paths=self.paths,
            reports_dir=self.reports_dir,
            filename_prefix=prefix,
        )
        return [
            ReportArtifact(kind="json", path=json_path),
            ReportArtifact(kind="markdown", path=md_path),
        ]
