"""Minimal config loading boundary for the standalone assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import RuntimePaths, resolve_runtime_paths


@dataclass(frozen=True)
class AssistantConfig:
    """Parsed assistant configuration with resolved runtime paths."""

    profile: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    documents: dict[str, Any] = field(default_factory=dict)
    runtime: RuntimePaths | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def document_paths(self) -> dict[str, Any]:
        """Compatibility alias for callers that name the document section explicitly."""

        return self.documents


def _as_dict(value: Any, section: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{section} must be a mapping")
    return dict(value)


def _resolve_document_value(value: Any, base_dir: Path | None) -> Any:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text
    path = Path(value).expanduser()
    if base_dir is not None and not path.is_absolute():
        return base_dir / path
    return path


def _resolve_documents(value: Any, base_dir: Path | None) -> dict[str, Any]:
    documents = _as_dict(value, "documents")
    return {
        str(key): _resolve_document_value(document_value, base_dir)
        for key, document_value in documents.items()
    }


def load_config(
    path: str | Path | None = None,
    workspace: str | Path | None = None,
) -> AssistantConfig:
    """Load a minimal YAML config and resolve paths without hidden defaults."""

    raw: dict[str, Any] = {}
    requested_config_path = Path(path).expanduser() if path is not None else None
    config_path = (
        resolve_runtime_paths(workspace=workspace, config=requested_config_path).config_file
        if requested_config_path is not None
        else None
    )

    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(config_path)
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ValueError("config root must be a mapping")
        raw = dict(parsed)

    profile = _as_dict(raw.get("profile"), "profile")
    defaults = _as_dict(raw.get("defaults"), "defaults")
    path_values = _as_dict(raw.get("paths"), "paths")

    runtime = resolve_runtime_paths(
        workspace=workspace,
        config=config_path,
        qa_bank=path_values.get("qa_bank"),
        browser_profile=path_values.get("browser_profile"),
        output_dir=path_values.get("output_dir"),
    )
    document_base = runtime.workspace
    if document_base is None and config_path is not None:
        document_base = config_path.parent
    documents = _resolve_documents(raw.get("documents"), document_base)

    return AssistantConfig(
        profile=profile,
        defaults=defaults,
        documents=documents,
        runtime=runtime,
        raw=raw,
    )
