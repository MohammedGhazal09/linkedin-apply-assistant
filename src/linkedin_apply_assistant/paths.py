"""Runtime path resolution for the standalone assistant."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

try:
    from platformdirs import user_cache_dir, user_config_dir, user_data_dir
except ModuleNotFoundError:

    def _windows_base(env_name: str, fallback: Path) -> Path:
        value = os.environ.get(env_name)
        return Path(value).expanduser() if value else fallback

    def user_config_dir(appname: str) -> str:
        base = _windows_base("APPDATA", Path.home() / ".config")
        return str(base / appname)

    def user_data_dir(appname: str) -> str:
        base = _windows_base("LOCALAPPDATA", Path.home() / ".local" / "share")
        return str(base / appname)

    def user_cache_dir(appname: str) -> str:
        base = _windows_base("LOCALAPPDATA", Path.home() / ".cache")
        return str(base / appname / "cache")


APP_NAME = "linkedin-apply-assistant"


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved paths for config, data, cache, browser profile, and outputs."""

    workspace: Path | None
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    config_file: Path
    qa_bank_file: Path
    browser_profile_dir: Path
    output_dir: Path
    reports_dir: Path


def _optional_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser()


def _resolve_under_workspace(workspace: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return workspace / path


def resolve_runtime_paths(
    workspace: str | Path | None = None,
    config: str | Path | None = None,
    qa_bank: str | Path | None = None,
    browser_profile: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> RuntimePaths:
    """Resolve runtime paths without touching the filesystem."""

    workspace_path = _optional_path(workspace)
    if workspace_path is not None:
        workspace_path = workspace_path.resolve()
        config_dir = workspace_path / "configs"
        data_dir = workspace_path / "data"
        cache_dir = workspace_path / ".cache"
        default_config = config_dir / "config.yml"
        default_qa_bank = config_dir / "qa_bank.yml"
        default_browser_profile = workspace_path / "browser-profile"
        default_output = workspace_path / "output"
    else:
        config_dir = Path(user_config_dir(APP_NAME))
        data_dir = Path(user_data_dir(APP_NAME))
        cache_dir = Path(user_cache_dir(APP_NAME))
        default_config = config_dir / "config.yml"
        default_qa_bank = config_dir / "qa_bank.yml"
        default_browser_profile = data_dir / "browser-profile"
        default_output = data_dir / "output"

    config_override = _optional_path(config)
    qa_bank_override = _optional_path(qa_bank)
    browser_override = _optional_path(browser_profile)
    output_override = _optional_path(output_dir)

    if workspace_path is not None:
        if config_override is not None:
            config_override = _resolve_under_workspace(workspace_path, config_override)
        if qa_bank_override is not None:
            qa_bank_override = _resolve_under_workspace(workspace_path, qa_bank_override)
        if browser_override is not None:
            browser_override = _resolve_under_workspace(workspace_path, browser_override)
        if output_override is not None:
            output_override = _resolve_under_workspace(workspace_path, output_override)

    resolved_output = output_override or default_output

    return RuntimePaths(
        workspace=workspace_path,
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        config_file=config_override or default_config,
        qa_bank_file=qa_bank_override or default_qa_bank,
        browser_profile_dir=browser_override or default_browser_profile,
        output_dir=resolved_output,
        reports_dir=resolved_output / "reports",
    )


def ensure_runtime_dirs(
    paths: RuntimePaths,
    *,
    include_browser_profile: bool = False,
) -> RuntimePaths:
    """Create runtime directories that are safe for local package operation."""

    for directory in (
        paths.config_dir,
        paths.data_dir,
        paths.cache_dir,
        paths.output_dir,
        paths.reports_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if include_browser_profile:
        paths.browser_profile_dir.mkdir(parents=True, exist_ok=True)
    return paths
