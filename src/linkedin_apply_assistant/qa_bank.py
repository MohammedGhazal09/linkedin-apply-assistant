"""Standalone Q&A matching with explicit data paths."""

from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any
import unicodedata

import yaml

from .paths import RuntimePaths
from .safety import domain_from_url, normalize_url_for_audit


MATCH_THRESHOLD = 0.75

STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "as",
    "and",
    "or",
    "but",
    "if",
    "your",
    "you",
    "our",
    "this",
    "that",
    "do",
    "does",
    "did",
    "what",
    "what's",
    "how",
    "have",
    "has",
    "be",
    "been",
    "being",
    "will",
    "would",
}


def normalize(text: str) -> str:
    """Strip accents and punctuation, lowercase, and collapse whitespace."""

    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def tokenize(text: str) -> set[str]:
    """Return content tokens for fuzzy question matching."""

    return {token for token in normalize(text).split() if token not in STOPWORDS and len(token) > 1}


def similarity(question: str, pattern: str) -> float:
    """Hybrid similarity using containment, token overlap, and sequence ratio."""

    norm_q = normalize(question)
    norm_p = normalize(pattern)
    if len(norm_p) >= 4 and norm_p in norm_q:
        return 0.95 + (len(norm_p) / max(len(norm_q), 1)) * 0.05

    tokens_q = tokenize(question)
    tokens_p = tokenize(pattern)
    if not tokens_p:
        return 0.0
    token_score = len(tokens_q & tokens_p) / len(tokens_p)
    seq_score = SequenceMatcher(None, norm_q, norm_p).ratio()
    return max(token_score * 0.85 + seq_score * 0.15, seq_score)


class QABank:
    """Application Q&A knowledge bank backed by explicit package paths."""

    def __init__(
        self,
        bank_file: str | Path | None = None,
        pending_file: str | Path | None = None,
        profile: dict[str, Any] | None = None,
    ) -> None:
        self.bank_file = Path(bank_file).expanduser() if bank_file is not None else None
        self.pending_file = Path(pending_file).expanduser() if pending_file is not None else None
        self.profile = profile or {}
        self.data = self._load()
        self.session_unknowns: list[dict[str, Any]] = []

    @classmethod
    def from_runtime_paths(
        cls,
        paths: RuntimePaths,
        profile: dict[str, Any] | None = None,
    ) -> "QABank":
        """Create a bank using standalone runtime locations."""

        return cls(
            bank_file=paths.qa_bank_file,
            pending_file=paths.data_dir / "pending_questions.md",
            profile=profile,
        )

    def _load(self) -> dict[str, Any]:
        if self.bank_file is None or not self.bank_file.exists():
            return {"qa_pairs": []}
        parsed = yaml.safe_load(self.bank_file.read_text(encoding="utf-8"))
        if parsed is None:
            return {"qa_pairs": []}
        if not isinstance(parsed, dict):
            raise ValueError("Q&A bank root must be a mapping")
        pairs = parsed.get("qa_pairs")
        if pairs is None:
            parsed["qa_pairs"] = []
        elif not isinstance(pairs, list):
            raise ValueError("qa_pairs must be a list")
        return dict(parsed)

    def _patterns_for(self, qa: dict[str, Any]) -> list[str]:
        patterns = qa.get("patterns", qa.get("question_patterns", []))
        if isinstance(patterns, str):
            return [patterns]
        if isinstance(patterns, list):
            return [str(pattern) for pattern in patterns if str(pattern).strip()]
        return []

    def _field_type_for(self, qa: dict[str, Any]) -> str:
        return str(qa.get("field_type") or qa.get("response_type") or "text")

    def _substitute_placeholders(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        if not text or "{" not in text:
            return text
        ctx = context or {}
        replacements = {
            "{company}": ctx.get("company", ""),
            "{role}": ctx.get("role", ""),
            "{portfolio}": self.profile.get("portfolio", ""),
            "{linkedin}": self.profile.get("linkedin", ""),
            "{github}": self.profile.get("github", ""),
            "{email}": self.profile.get("email", ""),
            "{phone}": self.profile.get("phone", ""),
            "{full_name}": self.profile.get("full_name", ""),
            "{first_name}": self.profile.get("first_name", ""),
            "{last_name}": self.profile.get("last_name", ""),
        }
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))
        return text

    def find_answer(
        self,
        question_text: str,
        field_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return a matched answer record, or ``None`` when no threshold match exists."""

        if not question_text:
            return None

        def type_compatible(bank_type: str, requested: str | None) -> bool:
            if not requested or not bank_type:
                return True
            bank_type = bank_type.lower()
            requested = requested.lower()
            if bank_type == requested:
                return True
            if bank_type == "radio_or_select" and requested in {"radio", "select"}:
                return True
            textish = {"text", "textarea", "email", "tel", "url", "number"}
            return bank_type in textish and requested in textish

        best: dict[str, Any] | None = None
        best_score = 0.0
        best_compatible: dict[str, Any] | None = None
        best_compatible_score = 0.0

        for qa in self.data.get("qa_pairs", []):
            if not isinstance(qa, dict):
                continue
            bank_type = self._field_type_for(qa)
            compatible = type_compatible(bank_type, field_type)
            for pattern in self._patterns_for(qa):
                score = similarity(question_text, pattern)
                if field_type and compatible:
                    score = min(score * 1.05, 1.0)
                candidate = {
                    "id": qa.get("id", "?"),
                    "answer": self._substitute_placeholders(str(qa.get("answer", "")), context),
                    "field_type": bank_type,
                    "matched_pattern": pattern,
                    "score": round(score, 3),
                }
                pattern_specificity = len(normalize(pattern))
                best_specificity = len(normalize(best["matched_pattern"])) if best else -1
                compatible_specificity = (
                    len(normalize(best_compatible["matched_pattern"])) if best_compatible else -1
                )
                if score > best_score or (
                    score == best_score and pattern_specificity > best_specificity
                ):
                    best_score = score
                    best = candidate
                if compatible and (
                    score > best_compatible_score
                    or (
                        score == best_compatible_score
                        and pattern_specificity > compatible_specificity
                    )
                ):
                    best_compatible_score = score
                    best_compatible = candidate

        if field_type:
            if best_compatible and best_compatible_score >= MATCH_THRESHOLD:
                return best_compatible
            return None
        if best and best_score >= MATCH_THRESHOLD:
            return best
        return None

    def log_pending(
        self,
        question_text: str,
        context: dict[str, Any] | None = None,
        field_type: str | None = None,
        is_required: bool = False,
    ) -> dict[str, Any]:
        """Record an unknown question in memory and append when a pending path exists."""

        ctx = context or {}
        normalized_url = normalize_url_for_audit(ctx.get("apply_url") or ctx.get("url") or "")
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "question": question_text.strip(),
            "company": ctx.get("company", "unknown"),
            "role": ctx.get("role", "unknown"),
            "ats": ctx.get("ats", "unknown"),
            "domain": ctx.get("domain") or domain_from_url(normalized_url),
            "field_type": field_type or "text",
            "required": is_required,
        }
        self.session_unknowns.append(entry)
        if self.pending_file is not None:
            self._append_pending(entry)
        return entry

    def _append_pending(self, entry: dict[str, Any]) -> None:
        if self.pending_file is None:
            return
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)
        existing_questions: set[str] = set()
        if self.pending_file.exists():
            content = self.pending_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                match = re.match(r"^###\s+Q:\s*(.+?)\s*$", line)
                if match:
                    existing_questions.add(normalize(match.group(1)))

        if normalize(entry["question"]) in existing_questions:
            self._increment_pending_counter(entry["question"], entry)
            return

        header_needed = not self.pending_file.exists() or self.pending_file.stat().st_size == 0
        with self.pending_file.open("a", encoding="utf-8") as handle:
            if header_needed:
                handle.write(self._pending_header())
            handle.write(self._format_pending_entry(entry))

    def _pending_header(self) -> str:
        return """# Pending Application Questions

These are questions the assistant encountered that are not in your selected Q&A bank yet.
Add a truthful answer below each question, then copy the final entry into your own Q&A bank.

Format for adding an answer:
```
**Answer:** Your answer here
**Field type:** text | textarea | number | select | radio_or_select
**Patterns:** synonym1, synonym2
```

---

"""

    def _format_pending_entry(self, entry: dict[str, Any]) -> str:
        seen_marker = f"[seen 1 time as of {entry['timestamp']}]"
        return f"""### Q: {entry["question"]}

- **First seen:** {entry["timestamp"]}
- **First context:** {entry["company"]} - {entry["role"]} ({entry["ats"]})
- **Domain:** {entry["domain"] or "unknown"}
- **Field type:** {entry["field_type"]}
- **Required:** {entry["required"]}
- **Stats:** {seen_marker}

**Answer:** _(fill in here)_

**Patterns:** _(optional - add synonyms separated by commas)_

---

"""

    def _increment_pending_counter(self, question: str, entry: dict[str, Any]) -> None:
        if self.pending_file is None or not self.pending_file.exists():
            return
        lines = self.pending_file.read_text(encoding="utf-8").splitlines(keepends=True)
        norm_target = normalize(question)
        for i, line in enumerate(lines):
            match = re.match(r"^###\s+Q:\s*(.+?)\s*$", line)
            if not match or normalize(match.group(1)) != norm_target:
                continue
            for j in range(i, min(i + 20, len(lines))):
                stat_match = re.match(
                    r"^- \*\*Stats:\*\* \[seen (\d+) times? as of [^\]]+\]\s*$",
                    lines[j],
                )
                if stat_match:
                    new_count = int(stat_match.group(1)) + 1
                    lines[j] = f"- **Stats:** [seen {new_count} times as of {entry['timestamp']}]\n"
                    self.pending_file.write_text("".join(lines), encoding="utf-8")
                    return
