"""Import-safe form primitives for the standalone assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


_real_print = print


def safe_print(*args: object, **kwargs: object) -> None:
    """Print text while tolerating narrow console encodings."""

    try:
        _real_print(*args, **kwargs)
    except UnicodeEncodeError:
        cleaned = []
        for arg in args:
            try:
                cleaned.append(str(arg))
            except Exception:
                cleaned.append(repr(arg))
        try:
            _real_print(*cleaned, **kwargs)
        except UnicodeEncodeError:
            ascii_cleaned = [
                str(arg).encode("ascii", errors="replace").decode("ascii") for arg in cleaned
            ]
            _real_print(*ascii_cleaned, **kwargs)


@dataclass
class FillResult:
    """Submit-free fill result shared by package fill-only surfaces."""

    filled: list[Any] = field(default_factory=list)
    required_empty: list[Any] = field(default_factory=list)
    unknown_questions: list[Any] = field(default_factory=list)
    reached_submit_step: bool = False
    surface: str = ""


@dataclass
class DetectionResult:
    """Read-only detection result for the currently visible application surface."""

    surface: str = "none"
    page: Any = None
    ats: str = ""
    job_context: dict[str, Any] = field(default_factory=dict)


ATS_PATTERNS: dict[str, tuple[str, ...]] = {
    "greenhouse": (
        r"boards\.greenhouse\.io",
        r"job-boards\.greenhouse\.io",
        r"greenhouse\.io/embed",
    ),
    "lever": (
        r"jobs\.lever\.co",
        r"lever\.co/[a-z0-9-]+/",
    ),
    "ashby": (
        r"jobs\.ashbyhq\.com",
        r"ashbyhq\.com",
    ),
    "workday": (
        r"\.myworkdayjobs\.com",
        r"workday\.com",
    ),
    "smartrecruiters": (
        r"smartrecruiters\.com",
        r"jobs\.smartrecruiters\.com",
    ),
    "recruitee": (r"\.recruitee\.com",),
    "workable": (
        r"apply\.workable\.com",
        r"jobs\.workable\.com",
    ),
    "bamboohr": (r"\.bamboohr\.com",),
    "icims": (r"\.icims\.com",),
    "taleo": (r"\.taleo\.net",),
    "successfactors": (
        r"\.successfactors\.com",
        r"jobs\.sap\.com",
    ),
    "personio": (
        r"\.personio\.de",
        r"jobs\.personio\.com",
    ),
    "teamtailor": (r"\.teamtailor\.com",),
    "jobvite": (
        r"jobs\.jobvite\.com",
        r"\.jobvite\.com",
    ),
    "resumator": (r"applytojob\.com",),
}


def detect_ats(url: str) -> str:
    """Return the known ATS identifier for a URL, or ``unknown``."""

    for ats, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url or "", re.IGNORECASE):
                return ats
    return "unknown"


def normalize_space(value: Any) -> str:
    """Collapse whitespace for stable text comparisons."""

    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_jobs(input_file: Path) -> list[dict[str, Any]]:
    """Load a JSON job list or object with a ``jobs`` list from an explicit path."""

    payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs = payload["jobs"]
    else:
        raise ValueError("job input must be a list or an object with a jobs list")
    if not all(isinstance(job, dict) for job in jobs):
        raise ValueError("every job entry must be an object")
    return list(jobs)


def load_applied_job_ids(path: Path) -> set[str]:
    """Load applied job ids from an explicit JSONL path."""

    applied_path = Path(path).expanduser()
    if not applied_path.exists():
        return set()
    ids: set[str] = set()
    for line in applied_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        job_id = str(payload.get("job_id") or "").strip()
        if job_id:
            ids.add(job_id)
    return ids


def append_applied_job_id(
    path: Path,
    job_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Append one applied job id to an explicit JSONL path."""

    clean_job_id = normalize_space(job_id)
    if not clean_job_id:
        raise ValueError("job_id is required")

    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "job_id": clean_job_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        payload["metadata"] = dict(metadata)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return target
