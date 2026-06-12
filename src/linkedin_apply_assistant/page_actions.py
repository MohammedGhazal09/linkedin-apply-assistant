"""Small page-operation helpers used by fill adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def safe_count(target: Any) -> int:
    """Return a best-effort count for a page object or locator."""

    try:
        count = target.count
        return int(count() if callable(count) else count)
    except Exception:
        return 0


def safe_visible(target: Any) -> bool:
    """Return whether a locator-like object appears visible."""

    try:
        visible = target.is_visible
        return bool(visible() if callable(visible) else visible)
    except Exception:
        return safe_count(target) > 0


def _first_locator(page: Any, selectors: Iterable[str]) -> Any | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
        except Exception:
            continue
        if safe_count(locator) > 0 and safe_visible(locator):
            return locator
    return None


def fill_first(page: Any, selectors: Iterable[str], value: Any) -> bool:
    """Fill the first matching control, supporting fake pages and Playwright-like pages."""

    if value is None or str(value).strip() == "":
        return False
    if hasattr(page, "fill_field"):
        return bool(page.fill_field(tuple(selectors), str(value)))
    locator = _first_locator(page, selectors)
    if locator is None:
        return False
    try:
        locator.fill(str(value), timeout=3000)
        return True
    except Exception:
        return False


def set_file_first(page: Any, selectors: Iterable[str], path: str | Path) -> bool:
    """Set a file input when available."""

    target = Path(path).expanduser()
    if not target.exists():
        return False
    if hasattr(page, "set_file"):
        return bool(page.set_file(tuple(selectors), target))
    locator = _first_locator(page, selectors)
    if locator is None:
        return False
    try:
        locator.set_input_files(str(target), timeout=3000)
        return True
    except Exception:
        return False


def visible_questions(page: Any) -> list[dict[str, Any]]:
    """Return fake-page questions when available, otherwise no browser-free questions."""

    questions = getattr(page, "visible_questions", None)
    if questions is None:
        questions = getattr(page, "questions", None)
    if callable(questions):
        questions = questions()
    if not questions:
        return []
    normalized: list[dict[str, Any]] = []
    for question in questions:
        if isinstance(question, dict):
            normalized.append(dict(question))
        else:
            normalized.append({"question": str(question), "field_type": "text", "required": False})
    return normalized


def fill_question(page: Any, question: dict[str, Any], answer: Any) -> bool:
    """Fill a fake-page custom question when supported."""

    if answer is None or str(answer).strip() == "":
        return False
    if hasattr(page, "fill_question"):
        return bool(page.fill_question(question, str(answer)))
    return False


def required_documents(page: Any) -> set[str]:
    """Return required document kinds advertised by a fake page."""

    value = getattr(page, "required_documents", set())
    if callable(value):
        value = value()
    return {str(item) for item in value or set()}
