from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PACKAGE_ROOT / "release-manifest.json"
GENERATED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "build",
    "dist",
}
PRIVATE_EXACT_PATHS = {
    "cv.md": "root CV document",
    "config/profile.yml": "root user profile",
    "modes/_profile.md": "root user personalization",
    "portals.yml": "root portal configuration",
    "data/applications.md": "root application tracker",
}
PRIVATE_ROOT_PREFIXES = {
    "reports/": "runtime reports",
    "output/": "runtime output",
    "browser-profile/": "browser profile",
    ".scrapling_browser_profile/": "browser profile",
}
PRIVATE_NAME_GLOBS = {
    "live_run_*.log": "live run log",
    "live_searchflow_*.log": "live search log",
    "_tmp_*.py": "scratch script",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
SENSITIVE_FILE_SUFFIX_REASONS = {
    ".cer": "sensitive key/certificate file",
    ".crt": "sensitive key/certificate file",
    ".key": "sensitive key/certificate file",
    ".p12": "sensitive key/certificate file",
    ".pem": "sensitive key/certificate file",
    ".pfx": "sensitive key/certificate file",
}
SECRET_PATTERNS = (
    (
        "private key block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
    (
        "secret assignment",
        re.compile(
            r"""(?im)^\s*[A-Za-z0-9_]*(?:api[_-]?key|token|password|secret|cookie|session)"""
            r"""[A-Za-z0-9_]*\s*[:=]\s*(?:"[^"'\n]{8,}"|'[^"'\n]{8,}'|"""
            r"""(?=[A-Za-z0-9_./+=:-]{8,}(?:\s|#|$))"""
            r"""(?=[A-Za-z0-9_./+=:-]*(?:[0-9]|[_./+=:-]))[A-Za-z0-9_./+=:-]{8,})"""
        ),
    ),
)


class ReleaseError(RuntimeError):
    """Raised when release candidate validation fails."""


@dataclass(frozen=True)
class ManifestFile:
    path: str
    category: str


@dataclass(frozen=True)
class ScanFinding:
    path: str
    category: str
    reason: str


@dataclass(frozen=True)
class ScanReport:
    root: Path
    findings: tuple[ScanFinding, ...]
    gitleaks_status: str


def _as_package_path(raw_path: str) -> PurePosixPath:
    path = PurePosixPath(raw_path)
    if path.is_absolute():
        raise ReleaseError(f"manifest path must be relative: {raw_path}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseError(f"manifest path must not traverse directories: {raw_path}")
    if "\\" in raw_path:
        raise ReleaseError(f"manifest path must use forward slashes: {raw_path}")
    return path


def _ensure_within_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ReleaseError(f"path resolves outside package root: {path}")
    return resolved


def _resolve_package_path(raw_path: str, root: Path = PACKAGE_ROOT) -> Path:
    posix_path = _as_package_path(raw_path)
    return _ensure_within_root(root / Path(*posix_path.parts), root)


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"manifest is not valid JSON: {exc}") from exc


def manifest_files(manifest: dict[str, Any]) -> list[ManifestFile]:
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ReleaseError("manifest must contain a non-empty files array")

    parsed: list[ManifestFile] = []
    seen: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            raise ReleaseError(f"files[{index}] must be an object")
        raw_path = item.get("path")
        category = item.get("category")
        if not isinstance(raw_path, str) or not raw_path:
            raise ReleaseError(f"files[{index}].path must be a non-empty string")
        if not isinstance(category, str) or not category:
            raise ReleaseError(f"files[{index}].category must be a non-empty string")

        path = _as_package_path(raw_path).as_posix()
        if path in seen:
            raise ReleaseError(f"duplicate manifest file: {path}")
        seen.add(path)
        parsed.append(ManifestFile(path=path, category=category))

    return parsed


def validate_manifest(path: Path = MANIFEST_PATH, root: Path = PACKAGE_ROOT) -> list[ManifestFile]:
    manifest = load_manifest(path)
    for field in ("schema_version", "package", "source_root", "files"):
        if field not in manifest:
            raise ReleaseError(f"manifest missing required field: {field}")
    if manifest["package"] != "linkedin-apply-assistant":
        raise ReleaseError("manifest package must be linkedin-apply-assistant")
    if manifest["source_root"] != ".":
        raise ReleaseError("manifest source_root must be .")

    files = manifest_files(manifest)
    missing: list[str] = []
    directories: list[str] = []
    for item in files:
        file_path = _resolve_package_path(item.path, root)
        if not file_path.exists():
            missing.append(item.path)
        elif not file_path.is_file():
            directories.append(item.path)

    if missing or directories:
        details = []
        details.extend(f"missing: {path}" for path in missing)
        details.extend(f"not a file: {path}" for path in directories)
        raise ReleaseError("manifest validation failed:\n" + "\n".join(details))

    return files


def copy_candidate(target: Path, manifest_path: Path = MANIFEST_PATH) -> int:
    files = validate_manifest(manifest_path)
    target_resolved = target.resolve()
    package_resolved = PACKAGE_ROOT.resolve()
    if target_resolved == package_resolved or package_resolved in target_resolved.parents:
        raise ReleaseError("candidate target must be outside the package root")
    if target.exists() and not target.is_dir():
        raise ReleaseError(f"candidate target must be a directory: {target}")
    if target.exists() and any(target.iterdir()):
        raise ReleaseError(f"candidate target must be empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    for item in files:
        source = _resolve_package_path(item.path)
        destination = target / Path(*PurePosixPath(item.path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    return len(files)


def _is_generated_path(path: Path) -> bool:
    return any(part in GENERATED_DIR_NAMES or part.endswith(".egg-info") for part in path.parts)


def _is_vcs_path(path: Path) -> bool:
    return any(part == ".git" for part in path.parts)


def _is_descendant_of(path: Path, possible_parent: Path) -> bool:
    return path == possible_parent or possible_parent in path.parents


def _dedupe_parent_paths(paths: Sequence[Path]) -> list[Path]:
    selected: list[Path] = []
    for path in sorted(set(paths), key=lambda item: (len(item.parts), item.as_posix())):
        if any(_is_descendant_of(path, parent) for parent in selected):
            continue
        selected.append(path)
    return selected


def generated_artifacts(root: Path = PACKAGE_ROOT) -> list[Path]:
    root_resolved = root.resolve()
    if not root_resolved.exists():
        raise ReleaseError(f"scan root does not exist: {root}")

    artifacts: list[Path] = []
    for path in root_resolved.rglob("*"):
        relative = path.relative_to(root_resolved)
        if path.is_dir() and _is_generated_path(relative):
            artifacts.append(relative)

    return _dedupe_parent_paths(artifacts)


def cleanup_generated(root: Path = PACKAGE_ROOT) -> list[Path]:
    root_resolved = root.resolve()
    removed: list[Path] = []
    for relative in generated_artifacts(root_resolved):
        target = _ensure_within_root(root_resolved / relative, root_resolved)
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(relative)
    return removed


def find_unlisted_files(
    manifest_path: Path = MANIFEST_PATH,
    root: Path = PACKAGE_ROOT,
    *,
    ignore_generated: bool = True,
) -> list[Path]:
    allowed = {item.path for item in manifest_files(load_manifest(manifest_path))}
    unlisted: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_vcs_path(relative):
            continue
        if ignore_generated and _is_generated_path(relative):
            continue
        if relative.as_posix() not in allowed:
            unlisted.append(relative)
    return sorted(unlisted)


def _private_path_reason(relative: Path) -> str | None:
    path = relative.as_posix()
    name = relative.name
    if path in PRIVATE_EXACT_PATHS:
        return PRIVATE_EXACT_PATHS[path]
    if name == ".env" or name.startswith(".env."):
        return "environment file"
    for prefix, reason in PRIVATE_ROOT_PREFIXES.items():
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return reason
    if any(part.startswith("linkedin_user_data") for part in relative.parts):
        return "browser profile"
    for pattern, reason in PRIVATE_NAME_GLOBS.items():
        if fnmatch.fnmatch(name, pattern):
            return reason
    return None


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def _secret_findings(path: Path, relative: Path) -> list[ScanFinding]:
    sensitive_suffix_reason = SENSITIVE_FILE_SUFFIX_REASONS.get(path.suffix.lower())
    if sensitive_suffix_reason is not None:
        return [
            ScanFinding(
                path=relative.as_posix(),
                category="secret",
                reason=sensitive_suffix_reason,
            )
        ]

    if not _is_text_file(path):
        return []
    text = _read_text(path)
    if text is None:
        return []

    findings: list[ScanFinding] = []
    for reason, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                ScanFinding(
                    path=relative.as_posix(),
                    category="secret",
                    reason=reason,
                )
            )
    return findings


def _fallback_scan_findings(root: Path) -> list[ScanFinding]:
    root_resolved = root.resolve()
    findings: list[ScanFinding] = []
    blocked_parents: list[Path] = []
    for path in sorted(root_resolved.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root_resolved)
        if any(_is_descendant_of(relative, parent) for parent in blocked_parents):
            continue
        if _is_vcs_path(relative):
            if path.is_dir():
                blocked_parents.append(relative)
            continue

        if _is_generated_path(relative):
            findings.append(
                ScanFinding(
                    path=relative.as_posix(),
                    category="generated",
                    reason="generated release blocker",
                )
            )
            if path.is_dir():
                blocked_parents.append(relative)
            continue

        private_reason = _private_path_reason(relative)
        if private_reason is not None:
            findings.append(
                ScanFinding(
                    path=relative.as_posix(),
                    category="private-path",
                    reason=private_reason,
                )
            )
            if path.is_dir():
                blocked_parents.append(relative)
            continue

        if path.is_file():
            findings.extend(_secret_findings(path, relative))

    return findings


def _relative_scan_path(raw_path: str, root: Path) -> str:
    normalized = raw_path.replace("\\", "/").strip()
    if not normalized:
        return "."

    path = Path(normalized)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return PurePosixPath(normalized).name or "."

    relative = PurePosixPath(normalized)
    if relative.parts and relative.parts[0] == ".":
        relative = PurePosixPath(*relative.parts[1:])
    return relative.as_posix() or "."


def _parse_gitleaks_report(report_path: Path, root: Path) -> list[ScanFinding]:
    try:
        raw_report = report_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not raw_report.strip():
        return []

    try:
        entries = json.loads(raw_report)
    except json.JSONDecodeError:
        return []
    if not isinstance(entries, list):
        return []

    findings: list[ScanFinding] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("File") or entry.get("file") or "."
        rule = entry.get("RuleID") or entry.get("Rule") or entry.get("Description")
        description = entry.get("Description")
        if isinstance(rule, str) and isinstance(description, str) and rule != description:
            reason = f"{rule}: {description}"
        elif isinstance(rule, str):
            reason = rule
        elif isinstance(description, str):
            reason = description
        else:
            reason = "gitleaks finding"
        findings.append(
            ScanFinding(
                path=_relative_scan_path(str(raw_path), root),
                category="secret",
                reason=reason,
            )
        )
    return findings


def _run_gitleaks(root: Path) -> tuple[str, list[ScanFinding]]:
    executable = shutil.which("gitleaks")
    if executable is None:
        return "gitleaks: unavailable (deterministic fallback scan ran)", []

    with tempfile.TemporaryDirectory(prefix="linkedin-apply-assistant-gitleaks-") as temp_dir:
        report_path = Path(temp_dir) / "gitleaks-report.json"
        command = [
            executable,
            "detect",
            "--no-git",
            "--source",
            str(root),
            "--redact",
            "--exit-code",
            "1",
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "gitleaks: failed to run", [
                ScanFinding(path=".", category="scanner", reason=f"gitleaks failed: {exc}")
            ]

        if result.returncode == 0:
            return "gitleaks: passed", []
        if result.returncode == 1:
            findings = _parse_gitleaks_report(report_path, root)
            if not findings:
                findings = [
                    ScanFinding(path=".", category="secret", reason="gitleaks detected leaks")
                ]
            return "gitleaks: findings detected", findings

        return "gitleaks: failed to run", [
            ScanFinding(
                path=".",
                category="scanner",
                reason=f"gitleaks exited {result.returncode}",
            )
        ]


def scan_tree(root: Path, *, include_gitleaks: bool = True) -> ScanReport:
    root_resolved = root.resolve()
    if not root_resolved.exists():
        raise ReleaseError(f"scan root does not exist: {root}")
    if not root_resolved.is_dir():
        raise ReleaseError(f"scan root must be a directory: {root}")

    findings = _fallback_scan_findings(root_resolved)
    if include_gitleaks:
        gitleaks_status, gitleaks_findings = _run_gitleaks(root_resolved)
        findings.extend(gitleaks_findings)
    else:
        gitleaks_status = "gitleaks: skipped"

    return ScanReport(
        root=root_resolved,
        findings=tuple(sorted(findings, key=lambda item: (item.path, item.category, item.reason))),
        gitleaks_status=gitleaks_status,
    )


def format_findings(findings: Sequence[ScanFinding]) -> str:
    if not findings:
        return "No release scan findings."

    lines = [
        "Release scan findings:",
        "Path | Category | Reason",
        "--- | --- | ---",
    ]
    for finding in findings:
        lines.append(f"{finding.path} | {finding.category} | {finding.reason}")
    return "\n".join(lines)


def _print_scan_report(report: ScanReport) -> None:
    print(report.gitleaks_status)
    print(format_findings(report.findings))


def run_manifest(args: argparse.Namespace) -> int:
    try:
        files = validate_manifest()
        print(f"Manifest OK: {MANIFEST_PATH.relative_to(PACKAGE_ROOT)} ({len(files)} files)")
        unlisted = find_unlisted_files()
        if unlisted:
            print("Unlisted non-generated package files:")
            for path in unlisted:
                print(f"- {path.as_posix()}")
            return 1
        if args.candidate:
            count = copy_candidate(Path(args.candidate))
            print(f"Candidate created: {args.candidate} ({count} files)")
        return 0
    except ReleaseError as exc:
        print(f"Release manifest failed: {exc}", file=sys.stderr)
        return 1


def run_clean(_args: argparse.Namespace) -> int:
    try:
        removed = cleanup_generated()
    except ReleaseError as exc:
        print(f"Release cleanup failed: {exc}", file=sys.stderr)
        return 1

    if not removed:
        print("No package-local generated release blockers found.")
        return 0

    print("Removed generated release blockers:")
    for path in removed:
        print(f"- {path.as_posix()}")
    return 0


def run_scan(args: argparse.Namespace) -> int:
    try:
        report = scan_tree(Path(args.path))
    except ReleaseError as exc:
        print(f"Release scan failed: {exc}", file=sys.stderr)
        return 1

    _print_scan_report(report)
    return 1 if report.findings else 0


def _prefixed_findings(label: str, findings: Sequence[ScanFinding]) -> tuple[ScanFinding, ...]:
    return tuple(
        ScanFinding(
            path=f"{label}:{finding.path}",
            category=finding.category,
            reason=finding.reason,
        )
        for finding in findings
    )


def run_verify(_args: argparse.Namespace) -> int:
    try:
        files = validate_manifest()
        print(f"Manifest OK: {MANIFEST_PATH.relative_to(PACKAGE_ROOT)} ({len(files)} files)")

        unlisted = find_unlisted_files(ignore_generated=True)
        if unlisted:
            print("Unlisted non-generated package files:")
            for path in unlisted:
                print(f"- {path.as_posix()}")
            return 1

        with tempfile.TemporaryDirectory(prefix="linkedin-apply-assistant-candidate-") as temp_dir:
            candidate = Path(temp_dir)
            count = copy_candidate(candidate)
            print(f"Candidate materialized: {candidate} ({count} files)")

            candidate_report = scan_tree(candidate)
            live_report = scan_tree(PACKAGE_ROOT)

            print("Candidate scan:")
            _print_scan_report(candidate_report)
            print("Live package scan:")
            _print_scan_report(live_report)

            findings = _prefixed_findings(
                "candidate", candidate_report.findings
            ) + _prefixed_findings("package", live_report.findings)
            if findings:
                print(format_findings(findings))
                print("Release verification failed.", file=sys.stderr)
                return 1

        print("Candidate removed after verification.")
        print("Release verification passed.")
        return 0
    except ReleaseError as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        return 1


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and prepare LinkedIn-apply-assistant release candidates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="Validate manifest or copy candidate")
    manifest_parser.add_argument(
        "--check",
        action="store_true",
        help="Validate manifest and detect unlisted non-generated files.",
    )
    manifest_parser.add_argument(
        "--candidate",
        help="Copy manifest allowlisted files to this empty candidate directory.",
    )

    subparsers.add_parser("clean", help="Remove package-local generated release blockers")
    scan_parser = subparsers.add_parser("scan", help="Scan a package tree or generated candidate")
    scan_parser.add_argument("path", help="Candidate or package directory to scan")
    subparsers.add_parser("verify", help="Run the full release-readiness gate")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "manifest":
        return run_manifest(args)
    if args.command == "clean":
        return run_clean(args)
    if args.command == "scan":
        return run_scan(args)
    if args.command == "verify":
        return run_verify(args)
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
