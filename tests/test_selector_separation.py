from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src" / "linkedin_apply_assistant"


def test_workflow_orchestration_stays_selector_light() -> None:
    text = (SRC / "workflows.py").read_text(encoding="utf-8")
    forbidden = [
        "locator(",
        ".fill(",
        ".click(",
        "button[",
        "input[",
        "textarea",
        "select[",
    ]

    failures = [term for term in forbidden if term in text]

    assert not failures


def test_fill_adapters_do_not_contain_live_submission_behavior() -> None:
    files = [
        SRC / "ats_handlers.py",
        SRC / "linkedin_layer.py",
        SRC / "page_actions.py",
    ]
    forbidden = [
        "try_" + "submit",
        "Submit" + " Application",
        "auto" + "-" + "submit",
        "un" + "attended",
        ".click(",
        'input[type="submit"]',
    ]

    failures: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lower_text = text.lower()
        for term in forbidden:
            haystack = lower_text if term.islower() else text
            needle = term.lower() if term.islower() else term
            if needle in haystack:
                failures.append(f"{path.name}: {term}")

    assert not failures, "\n".join(failures)
