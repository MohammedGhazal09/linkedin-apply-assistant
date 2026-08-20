from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES: dict[str, str] = {
    "src/linkedin_apply_assistant/origin_policy.py": r'''"""Strict public-origin validation for browser and ATS boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit


class OriginPolicyError(ValueError):
    """Raised when a URL or origin crosses the package trust boundary."""


@dataclass(frozen=True)
class OriginDecision:
    allowed: bool
    url: str = ""
    origin: str = ""
    hostname: str = ""
    ats: str = "unknown"
    reason: str = ""


_ATS_EXACT_HOSTS: dict[str, str] = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
    "smartrecruiters.com": "smartrecruiters",
    "jobs.smartrecruiters.com": "smartrecruiters",
    "apply.workable.com": "workable",
    "jobs.workable.com": "workable",
    "jobs.sap.com": "successfactors",
    "jobs.personio.com": "personio",
    "jobs.jobvite.com": "jobvite",
    "applytojob.com": "resumator",
}

_ATS_SUFFIX_HOSTS: tuple[tuple[str, str], ...] = (
    (".myworkdayjobs.com", "workday"),
    (".smartrecruiters.com", "smartrecruiters"),
    (".recruitee.com", "recruitee"),
    (".bamboohr.com", "bamboohr"),
    (".icims.com", "icims"),
    (".taleo.net", "taleo"),
    (".successfactors.com", "successfactors"),
    (".personio.de", "personio"),
    (".teamtailor.com", "teamtailor"),
    (".jobvite.com", "jobvite"),
    (".applytojob.com", "resumator"),
)


def _clean_hostname(hostname: str | None) -> str:
    if not hostname:
        raise OriginPolicyError("URL hostname is required")
    try:
        host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise OriginPolicyError("URL hostname is not valid IDNA") from exc
    if not host or any(ord(ch) < 33 for ch in host):
        raise OriginPolicyError("URL hostname is invalid")
    return host


def is_linkedin_host(hostname: str | None) -> bool:
    try:
        host = _clean_hostname(hostname)
    except OriginPolicyError:
        return False
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def classify_ats_hostname(hostname: str | None) -> str:
    try:
        host = _clean_hostname(hostname)
    except OriginPolicyError:
        return "unknown"
    exact = _ATS_EXACT_HOSTS.get(host)
    if exact:
        return exact
    for suffix, ats in _ATS_SUFFIX_HOSTS:
        if host.endswith(suffix) and host != suffix.lstrip("."):
            return ats
    return "unknown"


def classify_ats_url(url: str | None) -> str:
    try:
        parsed = urlsplit(str(url or ""))
    except ValueError:
        return "unknown"
    return classify_ats_hostname(parsed.hostname)


def _is_forbidden_ip(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def assert_public_dns(hostname: str) -> None:
    """Reject a hostname when its current DNS answers are non-public."""

    host = _clean_hostname(hostname)
    if _is_forbidden_ip(host) or host == "localhost" or host.endswith(".localhost"):
        raise OriginPolicyError("Private, loopback, and local browser targets are not allowed")
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # Browser navigation produces the actionable DNS error. Unknown DNS is not
        # reinterpreted as trusted; known ATS/linkedin host checks still apply.
        return
    for answer in answers:
        address = str(answer[4][0])
        if _is_forbidden_ip(address):
            raise OriginPolicyError("Hostname resolves to a non-public network address")


def canonical_https_url(
    value: str | None,
    *,
    preserve_query: bool = True,
    allow_local_test: bool = False,
) -> str:
    raw = str(value or "").strip()
    if not raw or any(ord(ch) < 32 for ch in raw):
        raise OriginPolicyError("A non-empty URL without control characters is required")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise OriginPolicyError("URL is malformed") from exc
    scheme = parsed.scheme.lower()
    host = _clean_hostname(parsed.hostname)
    local_test = allow_local_test and (
        host == "localhost" or host.endswith(".localhost") or _is_forbidden_ip(host)
    )
    if scheme != "https" and not (local_test and scheme == "http"):
        raise OriginPolicyError("Only HTTPS browser targets are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise OriginPolicyError("URLs containing user information are not allowed")
    if port is not None and port != (443 if scheme == "https" else 80):
        if not local_test:
            raise OriginPolicyError("Non-default browser target ports are not allowed")
    if not local_test and (
        _is_forbidden_ip(host) or host == "localhost" or host.endswith(".local")
    ):
        raise OriginPolicyError("Private, loopback, and local browser targets are not allowed")
    netloc = host
    if port is not None and port != (443 if scheme == "https" else 80):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    query = parsed.query if preserve_query else ""
    return urlunsplit(SplitResult(scheme, netloc, path, query, ""))


def origin_from_url(value: str | None, *, allow_local_test: bool = False) -> str:
    parsed = urlsplit(
        canonical_https_url(value, preserve_query=False, allow_local_test=allow_local_test)
    )
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def normalize_origins(values: Iterable[str] | None) -> frozenset[str]:
    origins: set[str] = set()
    for value in values or ():
        origins.add(origin_from_url(value))
    return frozenset(origins)


def validate_application_url(
    value: str | None,
    *,
    expected_ats: str | None = None,
    approved_origins: Iterable[str] | None = None,
    allow_linkedin: bool = True,
    resolve_public_dns: bool = False,
) -> OriginDecision:
    try:
        url = canonical_https_url(value)
        parsed = urlsplit(url)
        host = _clean_hostname(parsed.hostname)
        origin = origin_from_url(url)
        ats = "linkedin" if is_linkedin_host(host) else classify_ats_hostname(host)
        approved = normalize_origins(approved_origins)
        if ats == "linkedin" and allow_linkedin:
            allowed = True
        elif ats != "unknown":
            allowed = True
        else:
            allowed = origin in approved
        if not allowed:
            return OriginDecision(
                False,
                url=url,
                origin=origin,
                hostname=host,
                ats=ats,
                reason="Origin is neither a known application provider nor explicitly approved",
            )
        if expected_ats and expected_ats not in {"generic", ats}:
            return OriginDecision(
                False,
                url=url,
                origin=origin,
                hostname=host,
                ats=ats,
                reason=f"Origin does not match expected ATS {expected_ats!r}",
            )
        if resolve_public_dns:
            assert_public_dns(host)
        return OriginDecision(True, url=url, origin=origin, hostname=host, ats=ats)
    except OriginPolicyError as exc:
        return OriginDecision(False, reason=str(exc))


def require_application_url(value: str | None, **kwargs: object) -> OriginDecision:
    decision = validate_application_url(value, **kwargs)
    if not decision.allowed:
        raise OriginPolicyError(decision.reason or "Application origin is not trusted")
    return decision


__all__ = [
    "OriginDecision",
    "OriginPolicyError",
    "assert_public_dns",
    "canonical_https_url",
    "classify_ats_hostname",
    "classify_ats_url",
    "is_linkedin_host",
    "normalize_origins",
    "origin_from_url",
    "require_application_url",
    "validate_application_url",
]
''',
    "src/linkedin_apply_assistant/schemas.py": r'''"""Versioned, bounded configuration and job-input schemas."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .origin_policy import OriginPolicyError, canonical_https_url


SCHEMA_VERSION = 1
MAX_CONFIG_BYTES = 512 * 1024
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_TEXT = 10_000
PROFILE_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "full_name",
        "email",
        "phone",
        "location",
        "current_company",
        "linkedin",
        "portfolio",
        "github",
    }
)
DOCUMENT_FIELDS = frozenset({"resume", "cover_letter"})
PATH_FIELDS = frozenset({"qa_bank", "browser_profile", "output_dir"})
DEFAULT_FIELDS = frozenset(
    {
        "limit",
        "max_cycles",
        "mode",
        "visible_browser",
        "require_confirmation",
        "dry_run",
        "approved_origins",
    }
)


class SchemaError(ValueError):
    """Raised when local configuration or input does not match the public schema."""


@dataclass(frozen=True)
class ParsedConfig:
    profile: dict[str, Any]
    defaults: dict[str, Any]
    documents: dict[str, Path]
    paths: dict[str, Path | None]
    raw: dict[str, Any]


def read_text_limited(path: Path, *, limit: int) -> str:
    target = Path(path).expanduser()
    try:
        size = target.stat().st_size
    except FileNotFoundError:
        raise
    if size > limit:
        raise SchemaError(f"File exceeds the {limit}-byte input limit: {target}")
    return target.read_text(encoding="utf-8")


def load_json_limited(path: str | Path) -> Any:
    target = Path(path).expanduser()
    try:
        return json.loads(read_text_limited(target, limit=MAX_JSON_BYTES))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Invalid JSON in {target}: {exc.msg}") from exc


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SchemaError(f"{name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _bounded_text(value: Any, name: str, *, max_length: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        raise SchemaError(f"{name} must be text")
    text = str(value).strip()
    if len(text) > max_length:
        raise SchemaError(f"{name} exceeds {max_length} characters")
    if any(ord(ch) < 9 or 13 < ord(ch) < 32 for ch in text):
        raise SchemaError(f"{name} contains control characters")
    return text


def _reject_unknown(mapping: Mapping[str, Any], allowed: frozenset[str], name: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise SchemaError(f"{name} contains unknown field(s): {', '.join(unknown)}")


def _profile_from_legacy(profile: dict[str, Any]) -> dict[str, Any]:
    result = dict(profile)
    contact = result.pop("contact", None)
    if contact is not None:
        contact_map = _mapping(contact, "profile.contact")
        for old, new in (("email", "email"), ("phone", "phone"), ("website", "portfolio")):
            if old in contact_map and new not in result:
                result[new] = contact_map[old]
    if "name" in result and "full_name" not in result:
        result["full_name"] = result.pop("name")
    if result.get("full_name") and not result.get("first_name") and not result.get("last_name"):
        parts = str(result["full_name"]).strip().split(maxsplit=1)
        if parts:
            result["first_name"] = parts[0]
            result["last_name"] = parts[1] if len(parts) > 1 else ""
    result.pop("headline", None)
    return result


def normalize_profile(value: Any) -> dict[str, Any]:
    profile = _profile_from_legacy(_mapping(value, "profile"))
    _reject_unknown(profile, PROFILE_FIELDS, "profile")
    normalized = {key: _bounded_text(item, f"profile.{key}") for key, item in profile.items()}
    email = normalized.get("email", "")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise SchemaError("profile.email is not a valid email address")
    phone = normalized.get("phone", "")
    if phone and not re.fullmatch(r"[+0-9() .-]{7,32}", phone):
        raise SchemaError("profile.phone contains unsupported characters")
    for key in ("linkedin", "portfolio", "github"):
        if normalized.get(key):
            try:
                normalized[key] = canonical_https_url(normalized[key])
            except OriginPolicyError as exc:
                raise SchemaError(f"profile.{key}: {exc}") from exc
    return normalized


def confine_path(value: str | Path, *, base_dir: Path, name: str) -> Path:
    text = _bounded_text(value, name, max_length=4096)
    if not text:
        raise SchemaError(f"{name} must not be empty")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    resolved = candidate.resolve(strict=False)
    root = base_dir.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise SchemaError(f"{name} must stay inside workspace {root}")
    return resolved


def normalize_documents(value: Any, *, base_dir: Path) -> dict[str, Path]:
    documents = _mapping(value, "documents")
    # Historical portfolio entries belong to the profile, not file upload configuration.
    documents.pop("portfolio", None)
    _reject_unknown(documents, DOCUMENT_FIELDS, "documents")
    result: dict[str, Path] = {}
    for key, item in documents.items():
        if item in (None, ""):
            continue
        path = confine_path(item, base_dir=base_dir, name=f"documents.{key}")
        if path.suffix.lower() not in {".pdf", ".doc", ".docx", ".txt"}:
            raise SchemaError(f"documents.{key} has an unsupported file type")
        result[key] = path
    return result


def normalize_defaults(value: Any) -> dict[str, Any]:
    defaults = _mapping(value, "defaults")
    _reject_unknown(defaults, DEFAULT_FIELDS, "defaults")
    result: dict[str, Any] = {}
    for key, item in defaults.items():
        if key in {"limit", "max_cycles"}:
            try:
                result[key] = max(0, int(item))
            except (TypeError, ValueError) as exc:
                raise SchemaError(f"defaults.{key} must be an integer") from exc
        elif key in {"visible_browser", "require_confirmation", "dry_run"}:
            if not isinstance(item, bool):
                raise SchemaError(f"defaults.{key} must be true or false")
            result[key] = item
        elif key == "mode":
            mode = _bounded_text(item, "defaults.mode", max_length=32)
            if mode not in {"auto-watch", "on-demand"}:
                raise SchemaError("defaults.mode must be auto-watch or on-demand")
            result[key] = mode
        elif key == "approved_origins":
            if not isinstance(item, list):
                raise SchemaError("defaults.approved_origins must be a list")
            origins: list[str] = []
            from .origin_policy import origin_from_url

            for origin in item:
                try:
                    origins.append(origin_from_url(_bounded_text(origin, "approved origin")))
                except OriginPolicyError as exc:
                    raise SchemaError(f"Invalid approved origin: {exc}") from exc
            result[key] = origins
    return result


def parse_config_payload(value: Any, *, workspace: Path) -> ParsedConfig:
    payload = _mapping(value, "config root")
    allowed_root = frozenset({"schema_version", "profile", "defaults", "documents", "paths"})
    _reject_unknown(payload, allowed_root, "config root")
    version = payload.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise SchemaError(f"Unsupported config schema_version {version!r}; expected {SCHEMA_VERSION}")
    base = workspace.resolve(strict=False)
    path_values = _mapping(payload.get("paths"), "paths")
    _reject_unknown(path_values, PATH_FIELDS, "paths")
    paths: dict[str, Path | None] = {}
    for key, item in path_values.items():
        paths[key] = None if item in (None, "") else confine_path(
            item, base_dir=base, name=f"paths.{key}"
        )
    return ParsedConfig(
        profile=normalize_profile(payload.get("profile")),
        defaults=normalize_defaults(payload.get("defaults")),
        documents=normalize_documents(payload.get("documents"), base_dir=base),
        paths=paths,
        raw=dict(payload),
    )


def normalize_job_record(value: Any, *, require_description: bool = False) -> dict[str, Any]:
    job = _mapping(value, "job")
    allowed = frozenset(
        {
            "schema_version",
            "job_id",
            "linkedin_job_id",
            "id",
            "title",
            "role",
            "company",
            "url",
            "linkedin_url",
            "location",
            "description",
            "source",
            "search_url",
            "ats",
        }
    )
    _reject_unknown(job, allowed, "job")
    version = job.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise SchemaError(f"Unsupported job schema_version {version!r}")
    result = {
        "job_id": _bounded_text(
            job.get("job_id") or job.get("linkedin_job_id") or job.get("id"), "job.job_id", max_length=256
        ),
        "title": _bounded_text(job.get("title") or job.get("role"), "job.title", max_length=500),
        "company": _bounded_text(job.get("company"), "job.company", max_length=500),
        "url": _bounded_text(job.get("url") or job.get("linkedin_url"), "job.url", max_length=4096),
        "location": _bounded_text(job.get("location"), "job.location", max_length=500),
        "description": _bounded_text(job.get("description"), "job.description"),
        "source": _bounded_text(job.get("source") or "linkedin", "job.source", max_length=128),
        "search_url": _bounded_text(job.get("search_url"), "job.search_url", max_length=4096),
        "ats": _bounded_text(job.get("ats"), "job.ats", max_length=128),
    }
    required = ["title", "company", "url", "location"]
    if require_description:
        required.append("description")
    missing = [key for key in required if not result[key]]
    if missing:
        raise SchemaError(f"Job missing required field(s): {', '.join(missing)}")
    if result["url"]:
        try:
            result["url"] = canonical_https_url(result["url"])
        except OriginPolicyError as exc:
            raise SchemaError(f"job.url: {exc}") from exc
    if result["search_url"]:
        try:
            result["search_url"] = canonical_https_url(result["search_url"])
        except OriginPolicyError as exc:
            raise SchemaError(f"job.search_url: {exc}") from exc
    return result


__all__ = [
    "MAX_CONFIG_BYTES",
    "MAX_JSON_BYTES",
    "ParsedConfig",
    "SCHEMA_VERSION",
    "SchemaError",
    "confine_path",
    "load_json_limited",
    "normalize_job_record",
    "normalize_profile",
    "parse_config_payload",
    "read_text_limited",
]
''',
    "src/linkedin_apply_assistant/storage.py": r'''"""Private, atomic local storage primitives."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import threading
from typing import Iterator


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve(strict=False))
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def private_mkdir(path: str | Path) -> Path:
    target = Path(path).expanduser()
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.is_symlink():
        raise OSError(f"Refusing symlink directory: {target}")
    try:
        target.chmod(0o700)
    except OSError:
        pass
    return target


def _assert_safe_target(path: Path) -> None:
    if path.exists() and path.is_symlink():
        raise OSError(f"Refusing symlink file target: {path}")
    parent = path.parent
    private_mkdir(parent)
    resolved_parent = parent.resolve(strict=True)
    if resolved_parent != parent.resolve(strict=False):
        raise OSError(f"Refusing redirected output directory: {parent}")


def atomic_private_write(path: str | Path, content: str | bytes) -> Path:
    target = Path(path).expanduser()
    _assert_safe_target(target)
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    lock = _lock_for(target)
    with lock:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        temporary = Path(temporary_name)
        try:
            try:
                os.fchmod(descriptor, 0o600)
            except OSError:
                pass
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            try:
                target.chmod(0o600)
            except OSError:
                pass
            try:
                directory_fd = os.open(target.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)
    return target


@contextmanager
def process_local_lock(path: str | Path) -> Iterator[None]:
    with _lock_for(Path(path).expanduser()):
        yield


__all__ = ["atomic_private_write", "private_mkdir", "process_local_lock"]
''',
    "src/linkedin_apply_assistant/paths.py": r'''"""Runtime path resolution with workspace confinement and private permissions."""

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
        return str(_windows_base("APPDATA", Path.home() / ".config") / appname)

    def user_data_dir(appname: str) -> str:
        return str(_windows_base("LOCALAPPDATA", Path.home() / ".local" / "share") / appname)

    def user_cache_dir(appname: str) -> str:
        return str(_windows_base("LOCALAPPDATA", Path.home() / ".cache") / appname / "cache")

from .storage import private_mkdir


APP_NAME = "linkedin-apply-assistant"


@dataclass(frozen=True)
class RuntimePaths:
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
    return None if value is None else Path(value).expanduser()


def _workspace_path(workspace: Path, candidate: Path, name: str) -> Path:
    target = candidate if candidate.is_absolute() else workspace / candidate
    resolved = target.resolve(strict=False)
    root = workspace.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"{name} must stay inside workspace {root}")
    return resolved


def resolve_runtime_paths(
    workspace: str | Path | None = None,
    config: str | Path | None = None,
    qa_bank: str | Path | None = None,
    browser_profile: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> RuntimePaths:
    workspace_path = _optional_path(workspace)
    if workspace_path is not None:
        workspace_path = workspace_path.resolve(strict=False)
        config_dir = workspace_path / "configs"
        data_dir = workspace_path / "data"
        cache_dir = workspace_path / ".cache"
        defaults = {
            "config": config_dir / "config.yml",
            "qa_bank": config_dir / "qa_bank.yml",
            "browser_profile": workspace_path / "browser-profile",
            "output": workspace_path / "output",
        }
    else:
        config_dir = Path(user_config_dir(APP_NAME)).expanduser()
        data_dir = Path(user_data_dir(APP_NAME)).expanduser()
        cache_dir = Path(user_cache_dir(APP_NAME)).expanduser()
        defaults = {
            "config": config_dir / "config.yml",
            "qa_bank": config_dir / "qa_bank.yml",
            "browser_profile": data_dir / "browser-profile",
            "output": data_dir / "output",
        }

    overrides = {
        "config": _optional_path(config),
        "qa_bank": _optional_path(qa_bank),
        "browser_profile": _optional_path(browser_profile),
        "output": _optional_path(output_dir),
    }
    resolved: dict[str, Path] = {}
    for name, default in defaults.items():
        candidate = overrides[name] or default
        if workspace_path is not None:
            candidate = _workspace_path(workspace_path, candidate, name)
        resolved[name] = candidate.resolve(strict=False)
    output = resolved["output"]
    return RuntimePaths(
        workspace=workspace_path,
        config_dir=config_dir.resolve(strict=False),
        data_dir=data_dir.resolve(strict=False),
        cache_dir=cache_dir.resolve(strict=False),
        config_file=resolved["config"],
        qa_bank_file=resolved["qa_bank"],
        browser_profile_dir=resolved["browser_profile"],
        output_dir=output,
        reports_dir=output / "reports",
    )


def ensure_runtime_dirs(paths: RuntimePaths, *, include_browser_profile: bool = False) -> RuntimePaths:
    for directory in (
        paths.config_dir,
        paths.data_dir,
        paths.cache_dir,
        paths.output_dir,
        paths.reports_dir,
    ):
        private_mkdir(directory)
    if include_browser_profile:
        private_mkdir(paths.browser_profile_dir)
    return paths


__all__ = ["APP_NAME", "RuntimePaths", "ensure_runtime_dirs", "resolve_runtime_paths"]
''',
    "src/linkedin_apply_assistant/config.py": r'''"""Versioned configuration loading with explicit path precedence."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import RuntimePaths, resolve_runtime_paths
from .schemas import MAX_CONFIG_BYTES, SchemaError, parse_config_payload, read_text_limited


@dataclass(frozen=True)
class AssistantConfig:
    profile: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    documents: dict[str, Any] = field(default_factory=dict)
    runtime: RuntimePaths | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def document_paths(self) -> dict[str, Any]:
        return self.documents


def load_config(
    path: str | Path | None = None,
    workspace: str | Path | None = None,
    *,
    load_default: bool = True,
) -> AssistantConfig:
    preliminary = resolve_runtime_paths(workspace=workspace, config=path)
    config_path = preliminary.config_file
    if path is None and (not load_default or not config_path.exists()):
        return AssistantConfig(runtime=preliminary)
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    try:
        parsed = yaml.safe_load(read_text_limited(config_path, limit=MAX_CONFIG_BYTES))
    except yaml.YAMLError as exc:
        raise SchemaError(f"Invalid YAML in {config_path}: {exc}") from exc
    payload = {} if parsed is None else parsed
    workspace_root = preliminary.workspace or config_path.parent
    normalized = parse_config_payload(payload, workspace=workspace_root)
    configured_paths = normalized.paths
    runtime = resolve_runtime_paths(
        workspace=workspace,
        config=config_path,
        qa_bank=configured_paths.get("qa_bank"),
        browser_profile=configured_paths.get("browser_profile"),
        output_dir=configured_paths.get("output_dir"),
    )
    return AssistantConfig(
        profile=normalized.profile,
        defaults=normalized.defaults,
        documents=dict(normalized.documents),
        runtime=runtime,
        raw=normalized.raw,
    )


__all__ = ["AssistantConfig", "load_config"]
''',
    "src/linkedin_apply_assistant/safety.py": r'''"""No-submit policy, bounded metadata, strict origins, and automation limits."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .contracts import SubmissionResult, SubmitDecision
from .origin_policy import (
    OriginPolicyError,
    classify_ats_url,
    is_linkedin_host,
    origin_from_url,
    require_application_url,
    validate_application_url,
)


POLICY_NAME = "no-submit-policy"
POLICY_VERSION = "2026-08-20"
DISABLED_SUBMISSION_REASON = "Browser submission is disabled in this package boundary."
FUTURE_SUBMIT_POLICY = (
    "Any future submit-capable release must require per-application interactive "
    "confirmation immediately before the specific application is sent. Broad approvals, "
    "background sending, and unattended modes are outside this package boundary."
)
SEARCH_LIMIT_DEFAULT = 10
SEARCH_LIMIT_CAP = 25
ASSIST_CYCLES_DEFAULT = 1
ASSIST_CYCLES_CAP = 25
BROWSER_PROFILE_WARNING = (
    "Browser profile warning: visible browser profiles can contain cookies, sessions, "
    "and local form data. Keep the profile directory local, ignored, and under your control."
)
RISK_STATUSES = frozenset(
    {"login", "mfa", "checkpoint", "captcha", "rate_limited", "throttled", "blocked_origin"}
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def domain_from_url(url: str | None) -> str:
    value = str(url or "").strip()
    try:
        hostname = urlsplit(value).hostname
    except ValueError:
        hostname = None
    if not hostname and "://" not in value and "/" not in value:
        hostname = value
    return (hostname or "").lower().rstrip(".")


def normalize_url_for_audit(url: str | None) -> str:
    """Keep only the canonical origin; paths and queries can contain private identifiers."""

    try:
        return origin_from_url(url)
    except OriginPolicyError:
        return ""


def clamp_search_limit(value: int | str | None) -> int:
    return _clamp_non_negative_int(value, SEARCH_LIMIT_CAP)


def clamp_assist_cycles(value: int | str | None) -> int:
    return _clamp_non_negative_int(value, ASSIST_CYCLES_CAP)


def _clamp_non_negative_int(value: int | str | None, cap: int) -> int:
    try:
        parsed = int(value) if value is not None else 0
    except (TypeError, ValueError):
        parsed = 0
    return min(max(parsed, 0), cap)


def backoff_delay(attempt: int, *, base_seconds: float = 0.25, cap_seconds: float = 5.0) -> float:
    if attempt <= 0:
        return 0.0
    return min(float(base_seconds * (2 ** (attempt - 1))), float(cap_seconds))


class DisabledSubmissionPolicy:
    policy = POLICY_NAME

    def decide(self, action: str, context: dict[str, Any] | None = None) -> SubmissionResult:
        _ = action, context
        return SubmissionResult(status="disabled", reason=DISABLED_SUBMISSION_REASON, allowed=False)

    def submit_decision(
        self,
        action: str,
        *,
        command: str = "apply",
        context: dict[str, Any] | None = None,
        confirmation_state: str = "",
    ) -> SubmitDecision:
        ctx = dict(context or {})
        url = normalize_url_for_audit(ctx.get("url") or ctx.get("apply_url") or "")
        return SubmitDecision(
            timestamp=utc_timestamp(),
            command=command,
            policy=f"{POLICY_NAME}@{POLICY_VERSION}",
            action=str(action or "submit"),
            allowed=False,
            status="disabled",
            reason=DISABLED_SUBMISSION_REASON,
            company=str(ctx.get("company") or ""),
            role=str(ctx.get("role") or ctx.get("title") or ""),
            url=url,
            domain=domain_from_url(url or ctx.get("domain") or ""),
            ats=str(ctx.get("ats") or classify_ats_url(ctx.get("apply_url") or "")),
            confirmation_state=str(confirmation_state or "not_confirmed"),
        )

    def audit_event(self, action: str, **kwargs: Any) -> dict[str, Any]:
        return asdict(self.submit_decision(action, **kwargs))


def disabled_submit_audit_payload(
    *,
    command: str = "apply",
    action: str = "submit",
    context: dict[str, Any] | None = None,
    confirmation_state: str = "",
) -> dict[str, Any]:
    decision = DisabledSubmissionPolicy().audit_event(
        action,
        command=command,
        context=context,
        confirmation_state=confirmation_state,
    )
    event = {"type": "submit_decision", **decision}
    return {
        "schema_version": 1,
        "command": command,
        "timestamp": decision["timestamp"],
        "decision": decision,
        "events": [event],
        "summary": {
            "command": command,
            "policy": decision["policy"],
            "action": action,
            "status": decision["status"],
            "allowed": False,
            "submitted": 0,
            "reason": decision["reason"],
            "confirmation_state": decision["confirmation_state"],
        },
    }


__all__ = [
    "ASSIST_CYCLES_CAP",
    "ASSIST_CYCLES_DEFAULT",
    "BROWSER_PROFILE_WARNING",
    "DISABLED_SUBMISSION_REASON",
    "DisabledSubmissionPolicy",
    "FUTURE_SUBMIT_POLICY",
    "POLICY_NAME",
    "POLICY_VERSION",
    "RISK_STATUSES",
    "SEARCH_LIMIT_CAP",
    "SEARCH_LIMIT_DEFAULT",
    "backoff_delay",
    "clamp_assist_cycles",
    "clamp_search_limit",
    "disabled_submit_audit_payload",
    "domain_from_url",
    "normalize_url_for_audit",
    "require_application_url",
    "validate_application_url",
]
''',
    "src/linkedin_apply_assistant/redaction.py": r'''"""Allowlisted report serialization and Markdown-safe remote text."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import html
import re
from typing import Any

from .form_engine import normalize_space
from .safety import normalize_url_for_audit


REDACTION_MARKER = "[REDACTED]"
MARKDOWN_VALUE_LIMIT = 180

_ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "command",
        "timestamp",
        "search_url",
        "jobs",
        "events",
        "summary",
        "decision",
        "type",
        "action",
        "status",
        "surface",
        "ats",
        "blocked_reason",
        "unknown_questions",
        "required_empty",
        "required_empty_count",
        "unknown_count",
        "filled_count",
        "reached_submit_step",
        "feedback",
        "job",
        "identity",
        "job_id",
        "title",
        "role",
        "company",
        "location",
        "source",
        "url",
        "domain",
        "allowed",
        "policy",
        "reason",
        "confirmation_state",
        "submitted",
        "requested_limit",
        "effective_limit",
        "input_provided",
        "discovered",
        "deduplicated",
        "requested_cycles",
        "effective_cycles",
        "mode",
        "filled",
        "blocked",
        "duplicates",
        "question",
        "field_type",
        "required",
        "count",
        "total",
        "passed",
        "results",
        "pass",
        "missing",
        "integrity",
        "algorithm",
        "files",
        "sha256",
        "kind",
        "path",
    }
)
_URL_KEYS = frozenset({"url", "apply_url", "search_url"})
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "cookie",
    "credential",
    "auth",
    "session",
    "profile",
    "documents",
    "answer",
    "email",
    "phone",
    "raw",
    "html",
    "screenshot",
    "contents",
    "history",
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsessionid\s*=", re.IGNORECASE),
    re.compile(r"\bcookie\s*[:=]", re.IGNORECASE),
    re.compile(r"<\s*html\b", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),
)


def _normalized_key(key: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(key or "").strip().lower())


def _sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_remote_text(value: str, *, limit: int = 2_000) -> str:
    text = normalize_space(value)
    text = "".join(ch for ch in text if ch == "\t" or ord(ch) >= 32)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def sanitize_report_payload(payload: Any) -> Any:
    return _sanitize(payload, key="", root=True)


def _sanitize(value: Any, *, key: Any, root: bool = False) -> Any:
    normalized_key = _normalized_key(key)
    if key and (_sensitive_key(key) or normalized_key not in _ALLOWED_KEYS):
        return REDACTION_MARKER
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for child_key, child_value in value.items():
            child = str(child_key)
            result[child] = _sanitize(child_value, key=child)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize(item, key=key) for item in value]
    if isinstance(value, str):
        if normalized_key in _URL_KEYS or normalized_key.endswith("_url"):
            return normalize_url_for_audit(value)
        if any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS):
            return REDACTION_MARKER
        return _safe_remote_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_remote_text(str(value))


def sanitize_markdown_value(value: Any) -> str:
    sanitized = sanitize_report_payload(value)
    rendered = str(sanitized)
    rendered = _safe_remote_text(rendered, limit=MARKDOWN_VALUE_LIMIT)
    rendered = html.escape(rendered, quote=True)
    for token in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "#", "+", "-", "!", "|"):
        rendered = rendered.replace(token, f"\\{token}")
    return rendered


__all__ = ["REDACTION_MARKER", "sanitize_markdown_value", "sanitize_report_payload"]
''',
    "src/linkedin_apply_assistant/apply_reports.py": r'''"""Private atomic JSON/Markdown report writers with integrity metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .contracts import ReportArtifact
from .paths import RuntimePaths
from .redaction import sanitize_markdown_value, sanitize_report_payload
from .storage import atomic_private_write, private_mkdir


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%fZ")


def _safe_filename_prefix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip(".-")
    return safe or "report"


def _stem(prefix: str) -> str:
    return f"{_safe_filename_prefix(prefix)}_{_timestamp()}_{uuid4().hex[:12]}"


def resolve_reports_dir(
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> Path:
    if reports_dir is not None:
        return Path(reports_dir).expanduser()
    if paths is not None:
        return paths.reports_dir
    raise ValueError("reports_dir or paths is required")


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str).encode(
        "utf-8"
    )


def _markdown(report: dict[str, Any], stamp: str) -> str:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    events = report.get("events", []) if isinstance(report, dict) else []
    lines = [f"# Job Apply Assistant Report - {stamp}", ""]
    if isinstance(summary, dict):
        lines.extend(["## Summary", ""])
        for key in sorted(summary):
            lines.append(f"- **{sanitize_markdown_value(key)}:** {sanitize_markdown_value(summary[key])}")
        lines.append("")
    if isinstance(events, list):
        lines.extend(["## Events", ""])
        for event in events:
            if not isinstance(event, dict):
                continue
            job = event.get("job") if isinstance(event.get("job"), dict) else {}
            company = event.get("company") or job.get("company") or ""
            role = event.get("role") or event.get("title") or job.get("role") or job.get("title") or ""
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
                if event.get(key) not in (None, "", [], {}):
                    details.append(
                        f"{sanitize_markdown_value(key)}={sanitize_markdown_value(event[key])}"
                    )
            label = sanitize_markdown_value(event.get("type", "event"))
            context = " ".join(
                item for item in (sanitize_markdown_value(company), sanitize_markdown_value(role)) if item
            )
            suffix = f" - {'; '.join(details)}" if details else ""
            lines.append(f"- **{label}** {context}{suffix}".rstrip())
        lines.append("")
    return "\n".join(lines)


def _write_pair(
    report: dict[str, Any],
    *,
    target_dir: Path,
    filename_prefix: str,
) -> tuple[Path, Path]:
    private_mkdir(target_dir)
    safe = sanitize_report_payload(report)
    stamp = str(safe.get("timestamp") or datetime.now(timezone.utc).isoformat())
    stem = _stem(filename_prefix)
    json_path = target_dir / f"{stem}.json"
    markdown_path = target_dir / f"{stem}.md"
    json_data = _json_bytes(safe)
    markdown_data = _markdown(safe, stamp).encode("utf-8")
    atomic_private_write(json_path, json_data)
    atomic_private_write(markdown_path, markdown_data)
    integrity = {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": [
            {"kind": "json", "path": json_path.name, "sha256": hashlib.sha256(json_data).hexdigest()},
            {
                "kind": "markdown",
                "path": markdown_path.name,
                "sha256": hashlib.sha256(markdown_data).hexdigest(),
            },
        ],
    }
    atomic_private_write(target_dir / f"{stem}.integrity.json", _json_bytes(integrity))
    return json_path, markdown_path


def write_json_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
    filename_prefix: str = "report",
) -> Path:
    target_dir = resolve_reports_dir(paths=paths, reports_dir=reports_dir)
    private_mkdir(target_dir)
    target = target_dir / f"{_stem(filename_prefix)}.json"
    atomic_private_write(target, _json_bytes(sanitize_report_payload(report)))
    return target


def write_markdown_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
    filename_prefix: str = "report",
) -> Path:
    target_dir = resolve_reports_dir(paths=paths, reports_dir=reports_dir)
    private_mkdir(target_dir)
    target = target_dir / f"{_stem(filename_prefix)}.md"
    safe = sanitize_report_payload(report)
    atomic_private_write(target, _markdown(safe, str(safe.get("timestamp") or _timestamp())))
    return target


def write_dry_run_report(jobs: list[dict[str, Any]], report_path: str | Path) -> Path:
    payload = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(jobs),
        "passed": sum(1 for job in jobs if job.get("pass")),
        "results": jobs,
    }
    return atomic_private_write(
        Path(report_path).expanduser(), _json_bytes(sanitize_report_payload(payload))
    )


def write_assistive_session_report(
    report: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    _ = profile
    return _write_pair(
        report,
        target_dir=resolve_reports_dir(paths=paths, reports_dir=reports_dir),
        filename_prefix="assistive-session",
    )


def write_search_report(
    report: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
    reports_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    return _write_pair(
        report,
        target_dir=resolve_reports_dir(paths=paths, reports_dir=reports_dir),
        filename_prefix="search",
    )


class RuntimeReportSink:
    def __init__(
        self,
        *,
        paths: RuntimePaths | None = None,
        reports_dir: str | Path | None = None,
    ) -> None:
        self.paths = paths
        self.reports_dir = reports_dir

    def write(self, command: str, report: dict[str, Any]) -> list[ReportArtifact]:
        root = resolve_reports_dir(paths=self.paths, reports_dir=self.reports_dir)
        run_id = str(report.get("run_id") or uuid4().hex)
        payload = {"schema_version": 1, "run_id": run_id, **report}
        target_dir = root / _safe_filename_prefix(command) / _safe_filename_prefix(run_id)
        json_path, markdown_path = _write_pair(
            payload,
            target_dir=target_dir,
            filename_prefix="assistive-session" if command == "assist" else command,
        )
        return [
            ReportArtifact(kind="json", path=json_path),
            ReportArtifact(kind="markdown", path=markdown_path),
        ]


__all__ = [
    "RuntimeReportSink",
    "resolve_reports_dir",
    "write_assistive_session_report",
    "write_dry_run_report",
    "write_json_report",
    "write_markdown_report",
    "write_search_report",
]
''',
    "src/linkedin_apply_assistant/qa_bank.py": r'''"""Conservative Q&A matching with private, injection-safe pending logs."""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any
import unicodedata

import yaml

from .paths import RuntimePaths
from .redaction import sanitize_markdown_value
from .safety import domain_from_url, normalize_url_for_audit
from .storage import atomic_private_write, process_local_lock


MATCH_THRESHOLD = 0.88
SENSITIVE_TERMS = frozenset(
    {
        "sponsor",
        "sponsorship",
        "authorized",
        "authorization",
        "visa",
        "salary",
        "compensation",
        "disability",
        "veteran",
        "gender",
        "race",
        "ethnicity",
        "criminal",
        "conviction",
    }
)
PLACEHOLDER_PREFIXES = (
    "use a truthful",
    "use your",
    "fill in",
    "replace this",
    "your answer",
    "todo",
    "tbd",
)
STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "of", "in", "on", "at", "to", "for",
        "with", "by", "from", "as", "and", "or", "but", "if", "your", "you", "our", "this",
        "that", "do", "does", "did", "what", "how", "have", "has", "be", "been", "will", "would",
    }
)


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", normalized)).strip()


def tokenize(text: str) -> set[str]:
    return {token for token in normalize(text).split() if token not in STOPWORDS and len(token) > 1}


def similarity(question: str, pattern: str) -> float:
    q, p = normalize(question), normalize(pattern)
    if not q or not p:
        return 0.0
    if q == p:
        return 1.0
    q_tokens, p_tokens = tokenize(q), tokenize(p)
    if not p_tokens:
        return 0.0
    overlap = len(q_tokens & p_tokens) / max(len(q_tokens | p_tokens), 1)
    return max(SequenceMatcher(None, q, p).ratio(), overlap)


def _sensitive(text: str) -> bool:
    return bool(tokenize(text) & SENSITIVE_TERMS)


def _usable_answer(value: Any) -> bool:
    answer = str(value or "").strip()
    return bool(answer) and not answer.lower().startswith(PLACEHOLDER_PREFIXES)


class QABank:
    def __init__(
        self,
        bank_file: str | Path | None = None,
        pending_file: str | Path | None = None,
        profile: dict[str, Any] | None = None,
    ) -> None:
        self.bank_file = Path(bank_file).expanduser() if bank_file is not None else None
        self.pending_file = Path(pending_file).expanduser() if pending_file is not None else None
        self.profile = dict(profile or {})
        self.data = self._load()
        self.session_unknowns: list[dict[str, Any]] = []

    @classmethod
    def from_runtime_paths(cls, paths: RuntimePaths, profile: dict[str, Any] | None = None) -> "QABank":
        return cls(
            bank_file=paths.qa_bank_file,
            pending_file=paths.data_dir / "pending_questions.md",
            profile=profile,
        )

    def _load(self) -> dict[str, Any]:
        if self.bank_file is None or not self.bank_file.exists():
            return {"schema_version": 1, "qa_pairs": []}
        if self.bank_file.stat().st_size > 512 * 1024:
            raise ValueError("Q&A bank exceeds 512 KiB")
        parsed = yaml.safe_load(self.bank_file.read_text(encoding="utf-8"))
        if parsed is None:
            return {"schema_version": 1, "qa_pairs": []}
        if not isinstance(parsed, dict):
            raise ValueError("Q&A bank root must be a mapping")
        if parsed.get("schema_version", 1) != 1:
            raise ValueError("Unsupported Q&A bank schema_version")
        pairs = parsed.get("qa_pairs", [])
        if not isinstance(pairs, list):
            raise ValueError("qa_pairs must be a list")
        clean_pairs = []
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                raise ValueError(f"qa_pairs[{index}] must be a mapping")
            clean_pairs.append(dict(pair))
        return {**parsed, "qa_pairs": clean_pairs}

    def _patterns_for(self, qa: dict[str, Any]) -> list[str]:
        patterns = qa.get("patterns", qa.get("question_patterns", []))
        if isinstance(patterns, str):
            patterns = [patterns]
        return [str(pattern).strip() for pattern in patterns or [] if str(pattern).strip()]

    def _field_type_for(self, qa: dict[str, Any]) -> str:
        return str(qa.get("field_type") or qa.get("response_type") or "text").lower()

    def _substitute_placeholders(self, text: str, context: dict[str, Any] | None = None) -> str:
        ctx = context or {}
        replacements = {
            "company": ctx.get("company", ""),
            "role": ctx.get("role", ""),
            "portfolio": self.profile.get("portfolio", ""),
            "linkedin": self.profile.get("linkedin", ""),
            "github": self.profile.get("github", ""),
            "email": self.profile.get("email", ""),
            "phone": self.profile.get("phone", ""),
            "full_name": self.profile.get("full_name", ""),
            "first_name": self.profile.get("first_name", ""),
            "last_name": self.profile.get("last_name", ""),
        }
        for name, value in replacements.items():
            text = text.replace("{" + name + "}", str(value))
        return text

    @staticmethod
    def _type_compatible(bank_type: str, requested: str | None) -> bool:
        if not requested:
            return True
        requested = requested.lower()
        if bank_type == requested:
            return True
        if bank_type == "radio_or_select" and requested in {"radio", "select"}:
            return True
        return bank_type in {"text", "textarea"} and requested in {"text", "textarea"}

    def find_answer(
        self,
        question_text: str,
        field_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        question = str(question_text or "").strip()
        if not question:
            return None
        sensitive = _sensitive(question)
        best: dict[str, Any] | None = None
        best_score = 0.0
        for qa in self.data.get("qa_pairs", []):
            if not isinstance(qa, dict) or qa.get("enabled", True) is False:
                continue
            answer = self._substitute_placeholders(str(qa.get("answer", "")), context)
            if not _usable_answer(answer):
                continue
            bank_type = self._field_type_for(qa)
            if not self._type_compatible(bank_type, field_type):
                continue
            for pattern in self._patterns_for(qa):
                score = similarity(question, pattern)
                if sensitive and normalize(question) != normalize(pattern):
                    continue
                if sensitive and qa.get("confirmed") is not True:
                    continue
                if score > best_score:
                    best_score = score
                    best = {
                        "id": qa.get("id", "?"),
                        "answer": answer,
                        "field_type": bank_type,
                        "matched_pattern": pattern,
                        "score": round(score, 3),
                    }
        threshold = 1.0 if sensitive else MATCH_THRESHOLD
        return best if best and best_score >= threshold else None

    def log_pending(
        self,
        question_text: str,
        context: dict[str, Any] | None = None,
        field_type: str | None = None,
        is_required: bool = False,
    ) -> dict[str, Any]:
        ctx = context or {}
        url = normalize_url_for_audit(ctx.get("apply_url") or ctx.get("url") or "")
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": str(question_text).strip()[:1000],
            "company": str(ctx.get("company") or "unknown")[:300],
            "role": str(ctx.get("role") or ctx.get("title") or "unknown")[:300],
            "ats": str(ctx.get("ats") or "unknown")[:100],
            "domain": str(ctx.get("domain") or domain_from_url(url))[:253],
            "field_type": str(field_type or "text")[:64],
            "required": bool(is_required),
        }
        self.session_unknowns.append(entry)
        if self.pending_file is not None:
            self._append_pending(entry)
        return entry

    def _append_pending(self, entry: dict[str, Any]) -> None:
        assert self.pending_file is not None
        with process_local_lock(self.pending_file):
            existing = self.pending_file.read_text(encoding="utf-8") if self.pending_file.exists() else ""
            question_header = f"### Q: {sanitize_markdown_value(entry['question'])}"
            if question_header in existing:
                return
            if not existing:
                existing = (
                    "# Pending Application Questions\n\n"
                    "Unknown questions are recorded locally. Add only truthful, reviewed answers to "
                    "your private Q&A bank.\n\n---\n\n"
                )
            block = (
                f"{question_header}\n\n"
                f"- **First seen:** {sanitize_markdown_value(entry['timestamp'])}\n"
                f"- **First context:** {sanitize_markdown_value(entry['company'])} - "
                f"{sanitize_markdown_value(entry['role'])} ({sanitize_markdown_value(entry['ats'])})\n"
                f"- **Domain:** {sanitize_markdown_value(entry['domain'] or 'unknown')}\n"
                f"- **Field type:** {sanitize_markdown_value(entry['field_type'])}\n"
                f"- **Required:** {entry['required']}\n\n"
                "**Answer:** _(review and add to the private Q&A bank)_\n\n---\n\n"
            )
            atomic_private_write(self.pending_file, existing + block)


__all__ = ["MATCH_THRESHOLD", "QABank", "normalize", "similarity", "tokenize"]
''',
}


def apply() -> None:
    for relative, content in FILES.items():
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
