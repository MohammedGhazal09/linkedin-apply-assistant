from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

FILES: dict[str, str] = {
    "src/linkedin_apply_assistant/__init__.py": r'''"""Package identity for the local job-application assistant."""

__version__ = "0.1.5"

APP_DISPLAY_NAME = "Job Apply Assistant"
APP_PACKAGE_NAME = "linkedin-apply-assistant"
APP_IMPORT_NAME = "linkedin_apply_assistant"
APP_COMMAND_NAME = "linkedin-apply-assistant"

NON_AFFILIATION_NOTICE = (
    "Job Apply Assistant is an independent project and is not affiliated with, "
    "endorsed by, or sponsored by LinkedIn Corporation."
)
''',
    "src/linkedin_apply_assistant/cli.py": r'''"""User-visible CLI with strict schemas, no-submit behavior, and safe updates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import APP_PACKAGE_NAME, NON_AFFILIATION_NOTICE, __version__
from .apply_reports import RuntimeReportSink
from .ats_handlers import DisabledSubmissionPolicy
from .browser_sessions import PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND, VisibleBrowserSessionFactory
from .config import AssistantConfig, load_config
from .contracts import AssistRequest, SearchRequest
from .linkedin_layer import BrowserLinkedInDiscovery, CurrentSurfaceDetector, CurrentSurfaceFillAdapter, StaticLinkedInDiscovery
from .origin_policy import OriginPolicyError, origin_from_url
from .paths import RuntimePaths, resolve_runtime_paths
from .qa_bank import QABank
from .safety import BROWSER_PROFILE_WARNING, clamp_search_limit, disabled_submit_audit_payload
from .schemas import SchemaError, load_json_limited, normalize_job_record
from .workflows import compact_assist_feedback, run_assist_workflow, run_search_workflow


CONFIG_CHECK_COMMAND = "linkedin-apply-assistant config check"
CONFIG_EXAMPLE_PATH = "configs/config.example.yml"
QA_BANK_EXAMPLE_PATH = "configs/qa_bank.example.yml"
INSTALL_CHANNEL_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL"
NO_SUBMIT_HELP = (
    "Safety: browser workflows are visible, bounded, and no-submit. Unknown required "
    "questions and platform risk signals stop the workflow."
)


class CliError(Exception):
    pass


def _common_default(suppress: bool) -> Any:
    return argparse.SUPPRESS if suppress else None


def _add_common_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = _common_default(suppress_defaults)
    parser.add_argument("--workspace", default=default, help="Confined local workspace for private runtime data.")
    parser.add_argument("--config", default=default, help="Versioned YAML config path.")
    parser.add_argument("--qa-bank", default=default, help="Private Q&A bank YAML path.")
    parser.add_argument("--browser-profile", default=default, help="Private visible-browser profile directory.")
    parser.add_argument("--output-dir", default=default, help="Private local output directory.")
    parser.add_argument(
        "--allow-origin", action="append", default=argparse.SUPPRESS if suppress_defaults else [],
        help="Explicitly approve one additional HTTPS application origin. Repeat as needed.",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
        help="Print additional local command details.",
    )


def build_parser() -> argparse.ArgumentParser:
    root_common = argparse.ArgumentParser(add_help=False)
    sub_common = argparse.ArgumentParser(add_help=False)
    _add_common_options(root_common)
    _add_common_options(sub_common, suppress_defaults=True)
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="linkedin-apply-assistant",
        parents=[root_common],
        formatter_class=formatter,
        description="Independent local job-application assistant with visible, no-submit browser workflows.",
        epilog=f"{NON_AFFILIATION_NOTICE}\n\n{NO_SUBMIT_HELP}\n\nFirst run: {CONFIG_CHECK_COMMAND}",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subs = parser.add_subparsers(dest="command")

    config = subs.add_parser("config", parents=[sub_common], formatter_class=formatter, help="Read-only setup diagnostics.")
    config_subs = config.add_subparsers(dest="config_command")
    config_check = config_subs.add_parser("check", parents=[sub_common], formatter_class=formatter)
    config_check.set_defaults(handler=_handle_config_check)

    search = subs.add_parser("search", parents=[sub_common], formatter_class=formatter, help="Visible LinkedIn search discovery; no application submission.")
    search.add_argument("--query")
    search.add_argument("--location")
    search.add_argument("--limit", type=int)
    search.add_argument("--search-url")
    search.set_defaults(handler=_handle_search)

    assist = subs.add_parser("assist", parents=[sub_common], formatter_class=formatter, help="Visible fill-only assistance.")
    assist.add_argument("--start-url")
    assist.add_argument("--mode", choices=("auto-watch", "on-demand"))
    assist.add_argument("--max-cycles", type=int)
    assist.add_argument("--poll-seconds", type=float, default=0.25)
    assist.add_argument("--non-interactive", action="store_true", help="Do not wait for Enter in on-demand mode.")
    assist.set_defaults(handler=_handle_assist)

    apply_cmd = subs.add_parser("apply", parents=[sub_common], formatter_class=formatter, help="Validate candidates and write disabled-submit audit records.")
    apply_cmd.add_argument("--input", required=True, help="Candidate job JSON file.")
    apply_cmd.add_argument("--limit", type=int, default=10)
    apply_cmd.add_argument("--confirm-submit", action="store_true", help="Recorded for audit only; submission remains disabled.")
    apply_cmd.set_defaults(handler=_handle_apply)

    dry = subs.add_parser("dry-run", parents=[sub_common], formatter_class=formatter, help="Browser-free strict job-input validation.")
    dry.add_argument("--input", required=True)
    dry.set_defaults(handler=_handle_dry_run)

    report = subs.add_parser("report", parents=[sub_common], formatter_class=formatter, help="Browser-free local report summary.")
    report.add_argument("report_json")
    report.set_defaults(handler=_handle_report)

    update = subs.add_parser("update", parents=[sub_common], formatter_class=formatter, help="Inspect or run the supported package-manager update path.")
    update.add_argument("--method", choices=("auto", "npm", "powershell"), default="auto")
    update.add_argument("--check", action="store_true")
    update.set_defaults(handler=_handle_update)
    return parser


def _load_config(args: argparse.Namespace) -> AssistantConfig:
    try:
        return load_config(args.config, workspace=args.workspace, load_default=True)
    except (FileNotFoundError, SchemaError, ValueError) as exc:
        raise CliError(f"Invalid config: {exc}\nTry: {CONFIG_CHECK_COMMAND}") from exc


def _paths(args: argparse.Namespace, config: AssistantConfig) -> RuntimePaths:
    configured = config.runtime or resolve_runtime_paths(workspace=args.workspace)
    return resolve_runtime_paths(
        workspace=args.workspace,
        config=args.config or configured.config_file,
        qa_bank=args.qa_bank or configured.qa_bank_file,
        browser_profile=args.browser_profile or configured.browser_profile_dir,
        output_dir=args.output_dir or configured.output_dir,
    )


def _approved_origins(args: argparse.Namespace, config: AssistantConfig) -> tuple[str, ...]:
    values = [*(config.defaults.get("approved_origins") or []), *(args.allow_origin or [])]
    origins: list[str] = []
    for value in values:
        try:
            origins.append(origin_from_url(value))
        except OriginPolicyError as exc:
            raise CliError(f"Invalid --allow-origin value: {exc}") from exc
    return tuple(dict.fromkeys(origins))


def _diagnostic_rows(paths: RuntimePaths) -> list[tuple[str, str, Path, str]]:
    def status(path: Path, kind: str) -> str:
        if not path.exists():
            return "missing" if kind == "file" else "warning"
        if (kind == "file" and not path.is_file()) or (kind == "directory" and not path.is_dir()):
            return "warning"
        return "ok"
    return [
        ("config file", status(paths.config_file, "file"), paths.config_file, f"Copy {CONFIG_EXAMPLE_PATH}; schema_version is required."),
        ("Q&A bank", status(paths.qa_bank_file, "file"), paths.qa_bank_file, f"Copy {QA_BANK_EXAMPLE_PATH}; sensitive answers require exact confirmed matches."),
        ("browser profile", status(paths.browser_profile_dir, "directory"), paths.browser_profile_dir, "Created with private permissions by visible-browser workflows."),
        ("output directory", status(paths.output_dir, "directory"), paths.output_dir, "Created only when output is written."),
        ("reports directory", status(paths.reports_dir, "directory"), paths.reports_dir, "Atomic private reports and integrity manifests."),
        ("data directory", status(paths.data_dir, "directory"), paths.data_dir, "Private pending-question data."),
        ("cache directory", status(paths.cache_dir, "directory"), paths.cache_dir, "Private cache data."),
    ]


def _handle_config_check(args: argparse.Namespace) -> int:
    config = _load_config(args)
    paths = _paths(args, config)
    print("Config diagnostics")
    print("No files or directories were created.")
    print(f"{'status':<8} {'item':<18} path")
    for label, state, path, detail in _diagnostic_rows(paths):
        print(f"{state:<8} {label:<18} {path}")
        print(f"{'':<8} {'':<18} {detail}")
    print(f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND} before visible-browser workflows.")
    return 0


def _bank(paths: RuntimePaths, config: AssistantConfig) -> QABank:
    try:
        return QABank(
            bank_file=paths.qa_bank_file,
            pending_file=paths.data_dir / "pending_questions.md",
            profile=dict(config.profile),
        )
    except ValueError as exc:
        raise CliError(f"Invalid Q&A bank: {exc}") from exc


def _handle_search(args: argparse.Namespace) -> int:
    config = _load_config(args)
    paths = _paths(args, config)
    limit = args.limit if args.limit is not None else int(config.defaults.get("limit", 10))
    approved = _approved_origins(args, config)
    should_discover = limit > 0 and bool(args.search_url or args.query or args.location)
    discovery = BrowserLinkedInDiscovery(VisibleBrowserSessionFactory(paths, close_on_exit=True)) if should_discover else StaticLinkedInDiscovery([])
    try:
        result = run_search_workflow(
            SearchRequest(
                limit=limit, search_url=args.search_url, query=args.query, location=args.location,
                profile=dict(config.profile), approved_origins=approved, paths=paths,
            ),
            discovery,
            RuntimeReportSink(paths=paths),
            DisabledSubmissionPolicy(),
        )
    except (RuntimeError, ValueError, OriginPolicyError) as exc:
        raise CliError(str(exc)) from exc
    print("Search complete.")
    print(f"Requested limit: {limit}")
    print(f"Effective limit: {result.summary.get('effective_limit', limit)}")
    print(f"Jobs recorded: {len(result.jobs)}")
    for artifact in result.reports:
        print(f"{artifact.kind} report: {artifact.path}")
    return 0


def _handle_assist(args: argparse.Namespace) -> int:
    config = _load_config(args)
    paths = _paths(args, config)
    approved = _approved_origins(args, config)
    bank = _bank(paths, config)
    mode = args.mode or str(config.defaults.get("mode", "auto-watch"))
    cycles = args.max_cycles if args.max_cycles is not None else int(config.defaults.get("max_cycles", 1))
    if mode == "on-demand" and not args.non_interactive and sys.stdin.isatty():
        input("Review the visible page, then press Enter to run one fill-only inspection...")
    print(BROWSER_PROFILE_WARNING)
    try:
        result = run_assist_workflow(
            AssistRequest(
                start_url=args.start_url, mode=mode, max_cycles=cycles,
                poll_seconds=max(0.0, float(args.poll_seconds)), profile=dict(config.profile),
                documents=dict(config.documents), approved_origins=approved, paths=paths,
            ),
            VisibleBrowserSessionFactory(paths, close_on_exit=True),
            CurrentSurfaceDetector(profile=dict(config.profile), bank=bank, qa_context={"approved_origins": approved}),
            CurrentSurfaceFillAdapter(),
            RuntimeReportSink(paths=paths),
            DisabledSubmissionPolicy(),
            bank,
        )
    except (RuntimeError, ValueError, OriginPolicyError) as exc:
        raise CliError(str(exc)) from exc
    print("Assist complete.")
    for key in ("mode", "events", "filled", "blocked", "submitted"):
        print(f"{key.replace('_', ' ').title()}: {result.summary.get(key, 0)}")
    for event in result.events:
        print(compact_assist_feedback(event))
    for artifact in result.reports:
        print(f"{artifact.kind} report: {artifact.path}")
    return 0


def _candidate_jobs(path: str | Path) -> list[dict[str, Any]]:
    payload = load_json_limited(path)
    jobs = payload if isinstance(payload, list) else payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise SchemaError("Input must be a job list or an object with a jobs list")
    return [normalize_job_record(job, require_description=False) for job in jobs]


def _handle_apply(args: argparse.Namespace) -> int:
    config = _load_config(args)
    paths = _paths(args, config)
    try:
        jobs = _candidate_jobs(args.input)[: clamp_search_limit(args.limit)]
    except (FileNotFoundError, SchemaError) as exc:
        raise CliError(str(exc)) from exc
    events = []
    policy = DisabledSubmissionPolicy()
    confirmation = "flagged_but_disabled" if args.confirm_submit else "not_confirmed"
    for job in jobs:
        events.append(
            policy.audit_event(
                "submit",
                command="apply",
                context={
                    "company": job["company"], "role": job["title"], "url": job["url"], "ats": job["ats"],
                },
                confirmation_state=confirmation,
            )
        )
    report = disabled_submit_audit_payload(command="apply", confirmation_state=confirmation)
    report["events"] = [{"type": "submit_decision", **event} for event in events]
    report["summary"].update(
        {"requested_limit": args.limit, "input_provided": True, "count": len(events), "submitted": 0}
    )
    for artifact in RuntimeReportSink(paths=paths).write("apply", report):
        print(f"{artifact.kind} report: {artifact.path}")
    print(f"Validated candidates: {len(events)}")
    print("Browser submission remains disabled.")
    return 0


def _handle_dry_run(args: argparse.Namespace) -> int:
    try:
        jobs = _candidate_jobs(args.input)
    except (FileNotFoundError, SchemaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Dry run input valid: {len(jobs)} job(s)")
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    try:
        payload = load_json_limited(args.report_json)
    except (FileNotFoundError, SchemaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if isinstance(payload, dict):
        print("Report summary:")
        summary = payload.get("summary")
        if isinstance(summary, dict):
            for key in sorted(summary):
                print(f"{key}: {summary[key]}")
        if isinstance(payload.get("jobs"), list):
            print(f"jobs: {len(payload['jobs'])}")
        if isinstance(payload.get("events"), list):
            print(f"events: {len(payload['events'])}")
    elif isinstance(payload, list):
        print(f"Report summary: list items={len(payload)}")
    else:
        print(f"Report summary: {type(payload).__name__}")
    return 0


def _detect_update_method(requested: str) -> str:
    if requested != "auto":
        return requested
    channel = os.environ.get(INSTALL_CHANNEL_ENV, "").strip().lower()
    if channel in {"npm", "powershell"}:
        return channel
    return "npm" if shutil.which("npm") else "powershell"


def _handle_update(args: argparse.Namespace) -> int:
    method = _detect_update_method(args.method)
    print(f"Current version: {__version__}")
    print(f"Update method: {method}")
    if method == "powershell":
        print("Automatic PowerShell self-update is disabled because mutable remote scripts are not trusted.")
        print("Download a tagged install.ps1, inspect it, and provide its SHA-256 with -ExpectedSha256.")
        return 0 if args.check else 2
    npm = shutil.which("npm")
    command = [npm or "npm", "install", "-g", f"{APP_PACKAGE_NAME}@latest"]
    print(f"Update command: {' '.join(command)}")
    if args.check:
        return 0
    if npm is None:
        print("Error: npm is not available on PATH.", file=sys.stderr)
        return 2
    result = subprocess.run(command, check=False)
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        print(f"\nTry: {CONFIG_CHECK_COMMAND}")
        return 0
    if args.command == "config" and args.config_command is None:
        args.config_command = "check"
        args.handler = _handle_config_check
    try:
        return int(args.handler(args))
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "bin/linkedin-apply-assistant.mjs": r'''#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, delimiter, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const cliModule = "linkedin_apply_assistant.cli";
const userArgs = process.argv.slice(2);
const scriptDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(scriptDir, "..");
const localSrc = resolve(packageRoot, "src");
const launcherEnv = { ...process.env };
const candidates = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []], ["python", []]];

if (existsSync(localSrc)) {
  launcherEnv.PYTHONPATH = launcherEnv.PYTHONPATH
    ? `${localSrc}${delimiter}${launcherEnv.PYTHONPATH}`
    : localSrc;
}
launcherEnv.LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL = "npm";
launcherEnv.LINKEDIN_APPLY_ASSISTANT_NPM_PACKAGE_ROOT = packageRoot;

function runPython(command, args, options = {}) {
  return spawnSync(command, args, { env: launcherEnv, windowsHide: true, shell: false, ...options });
}

function guidance(reason) {
  console.error(`linkedin-apply-assistant could not start: ${reason}`);
  console.error("The npm package is a transparent launcher, not a hidden Python installer.");
  console.error(`Install the reviewed bundled Python source explicitly: python -m pip install "${packageRoot}"`);
}

let sawPython = false;
for (const [command, prefix] of candidates) {
  const version = runPython(command, [...prefix, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"], { stdio: "ignore" });
  if (version.error?.code === "ENOENT") continue;
  if (version.error || version.status !== 0) continue;
  sawPython = true;
  const probe = runPython(command, [...prefix, "-c", `import ${cliModule}`], { stdio: "ignore" });
  if (probe.status !== 0) continue;
  const result = runPython(command, [...prefix, "-m", cliModule, ...userArgs], { stdio: "inherit" });
  if (result.error) { guidance(result.error.message); process.exit(1); }
  if (result.signal) { console.error(`Python CLI exited after signal ${result.signal}`); process.exit(1); }
  process.exit(result.status ?? 1);
}
guidance(sawPython ? "Python 3.11+ was found, but the Python package is not importable." : "Python 3.11+ was not found on PATH.");
process.exit(1);
''',
    "install.ps1": r'''[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "linkedin-apply-assistant"),
    [string]$Ref = "v0.1.5",
    [string]$ExpectedSha256,
    [switch]$InstallBrowser,
    [switch]$NoPath,
    [switch]$Update,
    [switch]$CheckOnly
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$RepoOwner = "MohammedGhazal09"
$RepoName = "linkedin-apply-assistant"

function Write-Step { param([string]$Message) Write-Host "[job-apply-assistant] $Message" }

function Assert-ImmutableRef {
    param([string]$SourceRef)
    if ($SourceRef -match "^(main|master|develop|dev|refs/heads/)") {
        throw "Mutable branch refs are not allowed. Use a reviewed version tag or full 40-character commit SHA."
    }
    if ($SourceRef -notmatch "^v?\d+\.\d+\.\d+([-.][A-Za-z0-9.]+)?$" -and $SourceRef -notmatch "^[0-9a-fA-F]{40}$") {
        throw "Ref must be a semantic version tag or full 40-character commit SHA."
    }
}

function Get-ArchiveUrl {
    param([string]$SourceRef)
    Assert-ImmutableRef $SourceRef
    if ($SourceRef -match "^[0-9a-fA-F]{40}$") {
        return "https://github.com/$RepoOwner/$RepoName/archive/$SourceRef.zip"
    }
    return "https://github.com/$RepoOwner/$RepoName/archive/refs/tags/$SourceRef.zip"
}

function Get-Python {
    $candidates = @(
        @{ Command = "py"; Args = @("-3.11") }, @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() }, @{ Command = "python3"; Args = @() }
    )
    foreach ($candidate in $candidates) {
        try {
            & $candidate.Command @([string[]]$candidate.Args) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { continue }
    }
    throw "Python 3.11 or newer was not found."
}

function Add-UserPathEntry { param([string]$PathEntry)
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = if ($current) { $current -split [IO.Path]::PathSeparator } else { @() }
    if ($parts -notcontains $PathEntry) {
        $next = if ($current) { "$PathEntry$([IO.Path]::PathSeparator)$current" } else { $PathEntry }
        [Environment]::SetEnvironmentVariable("Path", $next, "User")
    }
}

$archiveUrl = Get-ArchiveUrl $Ref
$installRoot = [IO.Path]::GetFullPath($InstallDir)
$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("job-apply-assistant-" + [guid]::NewGuid())
$zipPath = Join-Path $tempDir "source.zip"
if ($CheckOnly) {
    Write-Step "Pinned source: $archiveUrl"
    Write-Step "Install directory: $installRoot"
    Write-Step "Expected SHA-256: $(if($ExpectedSha256){$ExpectedSha256}else{'required for installation'})"
    exit 0
}

try {
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri $archiveUrl -OutFile $zipPath
    $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $ExpectedSha256) {
        throw "Archive downloaded but not executed. SHA-256 is $actual. Inspect the tagged source and rerun with -ExpectedSha256 $actual."
    }
    if ($actual -ne $ExpectedSha256.ToLowerInvariant()) { throw "Archive SHA-256 mismatch." }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $tempDir -Force
    $expanded = Get-ChildItem -LiteralPath $tempDir -Directory | Where-Object { $_.Name -like "$RepoName-*" } | Select-Object -First 1
    if ($null -eq $expanded) { throw "Could not locate extracted source." }
    New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
    $sourceDir = Join-Path $installRoot "source"
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Move-Item $expanded.FullName $sourceDir
    $venvDir = Join-Path $installRoot ".venv"
    $python = Get-Python
    & $python.Command @([string[]]$python.Args) -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    & $venvPython -m pip install --require-virtualenv $sourceDir
    if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
    if ($InstallBrowser) { & $venvPython -m playwright install chromium; if ($LASTEXITCODE -ne 0) { throw "Chromium install failed." } }
    $binDir = Join-Path $installRoot "bin"; New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    @"
@echo off
set "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL=powershell"
"$venvPython" -m linkedin_apply_assistant.cli %*
"@ | Set-Content -LiteralPath (Join-Path $binDir "linkedin-apply-assistant.cmd") -Encoding ASCII
    if (-not $NoPath) { Add-UserPathEntry $binDir }
    Write-Step "Installed pinned, verified source to $installRoot"
} finally {
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
}
''',
    "configs/config.example.yml": r'''schema_version: 1

profile:
  first_name: "Example"
  last_name: "Candidate"
  full_name: "Example Candidate"
  email: "candidate@example.com"
  phone: null
  location: "Example City"
  current_company: null
  linkedin: "https://www.linkedin.com/in/example-candidate"
  portfolio: "https://example.com/portfolio"
  github: "https://github.com/example-candidate"

defaults:
  limit: 10
  max_cycles: 1
  mode: "on-demand"
  visible_browser: true
  require_confirmation: true
  dry_run: true
  approved_origins: []

documents:
  resume: "documents/resume.example.pdf"
  cover_letter: "documents/cover-letter.example.pdf"

paths:
  qa_bank: "configs/qa_bank.yml"
  browser_profile: "browser-profile"
  output_dir: "output"
''',
    "configs/qa_bank.example.yml": r'''schema_version: 1

# Copy this file to your ignored private workspace. Entries are disabled and blank
# by default so example text can never be submitted as if it were your answer.
qa_pairs:
  - id: work_authorization
    enabled: false
    confirmed: false
    question_patterns:
      - "Are you authorized to work in the target country?"
    answer: ""
    response_type: radio_or_select

  - id: sponsorship
    enabled: false
    confirmed: false
    question_patterns:
      - "Do you require sponsorship?"
    answer: ""
    response_type: radio_or_select

  - id: notice_period
    enabled: false
    confirmed: false
    question_patterns:
      - "What is your notice period?"
    answer: ""
    response_type: text

  - id: compensation_expectation
    enabled: false
    confirmed: false
    question_patterns:
      - "What are your salary expectations?"
    answer: ""
    response_type: text
''',
    "tests/test_security_regressions.py": r'''from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from linkedin_apply_assistant.apply_reports import RuntimeReportSink
from linkedin_apply_assistant.origin_policy import classify_ats_url, validate_application_url
from linkedin_apply_assistant.paths import resolve_runtime_paths
from linkedin_apply_assistant.qa_bank import QABank
from linkedin_apply_assistant.schemas import SchemaError, parse_config_payload


def test_ats_classification_uses_hostname_only() -> None:
    malicious = "https://attacker.example/jobs.lever.co/apply?next=https://boards.greenhouse.io"
    assert classify_ats_url(malicious) == "unknown"
    assert validate_application_url(malicious, expected_ats="lever").allowed is False


def test_private_and_credentialed_urls_are_rejected() -> None:
    for url in (
        "http://jobs.lever.co/example",
        "https://user:pass@jobs.lever.co/example",
        "https://127.0.0.1/apply",
        "file:///etc/passwd",
    ):
        assert validate_application_url(url).allowed is False


def test_config_paths_cannot_escape_workspace(tmp_path: Path) -> None:
    with pytest.raises(SchemaError, match="inside workspace"):
        parse_config_payload(
            {"schema_version": 1, "documents": {"resume": "../secret.pdf"}},
            workspace=tmp_path,
        )


def test_sensitive_qa_requires_exact_confirmed_pattern(tmp_path: Path) -> None:
    path = tmp_path / "qa.yml"
    path.write_text(
        """schema_version: 1
qa_pairs:
  - id: sponsorship
    confirmed: false
    patterns: [Do you require sponsorship?]
    answer: No
    field_type: select
""",
        encoding="utf-8",
    )
    bank = QABank(path)
    assert bank.find_answer("Do you require sponsorship?", field_type="select") is None
    path.write_text(path.read_text(encoding="utf-8").replace("confirmed: false", "confirmed: true"), encoding="utf-8")
    bank = QABank(path)
    assert bank.find_answer("Do you require sponsorship?", field_type="select")["answer"] == "No"
    assert bank.find_answer("Will you now or later need visa sponsorship?", field_type="select") is None


def test_runtime_reports_are_private_atomic_and_integrity_addressed(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(workspace=tmp_path)
    artifacts = RuntimeReportSink(paths=paths).write(
        "assist",
        {
            "command": "assist",
            "timestamp": "2026-08-20T00:00:00+00:00",
            "events": [{"type": "filled", "status": "filled", "company": "Example"}],
            "summary": {"submitted": 0},
        },
    )
    assert len(artifacts) == 2
    assert artifacts[0].path.parent == artifacts[1].path.parent
    manifests = list(artifacts[0].path.parent.glob("*.integrity.json"))
    assert len(manifests) == 1
    payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert payload["algorithm"] == "sha256"
    if os.name != "nt":
        assert artifacts[0].path.stat().st_mode & 0o077 == 0
        assert artifacts[0].path.parent.stat().st_mode & 0o077 == 0
''',
    "tests/test_browser_e2e.py": r'''from __future__ import annotations

from pathlib import Path

import pytest

from linkedin_apply_assistant.ats_handlers import fill_external_apply_page
from linkedin_apply_assistant.linkedin_layer import BrowserLinkedInDiscovery, fill_linkedin_easy_apply
from linkedin_apply_assistant.contracts import SearchRequest


pytestmark = pytest.mark.live


def _browser():
    api = pytest.importorskip("playwright.sync_api")
    manager = api.sync_playwright().start()
    try:
        browser = manager.chromium.launch(headless=True)
    except Exception:
        manager.stop()
        pytest.skip("Playwright Chromium is not installed")
    return manager, browser


def test_real_dom_multi_step_fill_stops_before_submit(tmp_path: Path) -> None:
    manager, browser = _browser()
    try:
        page = browser.new_page()
        html = """
        <html><body><div role='dialog'>
          <label>Email<input type='email' name='email' required></label>
          <button id='next'>Next</button>
        </div><script>
        window.submitted = false;
        document.querySelector('#next').onclick = () => {
          document.querySelector('[role=dialog]').innerHTML = `
            <label>Portfolio<input name='portfolio' required></label>
            <button type='submit' onclick='window.submitted=true'>Submit application</button>`;
        };
        </script></body></html>
        """
        page.route("https://www.linkedin.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
        page.goto("https://www.linkedin.com/jobs/view/1")
        result = fill_linkedin_easy_apply(
            page,
            {"email": "candidate@example.test", "portfolio": "https://portfolio.example"},
        )
        assert result.reached_submit_step is True
        assert page.locator('input[name="email"]').input_value() == "candidate@example.test"
        assert page.locator('input[name="portfolio"]').input_value() == "https://portfolio.example"
        assert page.evaluate("window.submitted") is False
    finally:
        browser.close()
        manager.stop()


def test_spoofed_ats_origin_is_blocked_before_pii_write() -> None:
    manager, browser = _browser()
    try:
        page = browser.new_page()
        page.route(
            "https://attacker.example/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<form><label>Email<input type=email name=email></label></form>",
            ),
        )
        page.goto("https://attacker.example/jobs.lever.co/apply")
        result = fill_external_apply_page(page, "lever", {"email": "private@example.test"})
        assert result.required_empty
        assert page.locator("input").input_value() == ""
    finally:
        browser.close()
        manager.stop()


def test_real_linkedin_job_discovery_extracts_cards() -> None:
    manager, browser = _browser()
    try:
        page = browser.new_page()
        page.route(
            "https://www.linkedin.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="""<ul><li data-job-id='123'><a href='https://www.linkedin.com/jobs/view/123/'>Engineer</a><span class='company'>Example</span><span class='location'>Remote</span></li></ul>""",
            ),
        )
        class Session:
            close_on_exit = False
            pages = [page]
            def open_url(self, url: str) -> None: page.goto(url)
            def close(self) -> None: pass
        class Factory:
            def open(self, request): return Session()
        jobs = BrowserLinkedInDiscovery(Factory()).discover(SearchRequest(limit=5, search_url="https://www.linkedin.com/jobs/search/"))
        assert jobs[0]["job_id"] == "123"
        assert jobs[0]["title"] == "Engineer"
    finally:
        browser.close()
        manager.stop()
''',
    "docs/audit-remediation.md": r'''# Comprehensive Audit Remediation

This change closes the repository-wide audit through shared enforcement boundaries rather than one-off checks.

## Browser and data-flow boundaries

- Real Playwright pages are inspected and filled through one production adapter also exercised by deterministic Chromium fixtures.
- ATS identity is derived only from a canonical HTTPS hostname. Path, query, fragment, user information, local/private addresses, and mismatched ATS claims cannot establish trust.
- Unknown external origins require explicit per-origin approval before any candidate field or document is written.
- Every Easy Apply step is rescanned. Unknown required controls stop the workflow; only Next, Continue, and Review can advance; final submission controls are never clicked.
- Login, MFA, CAPTCHA, checkpoint, throttling, and untrusted-origin states stop the bounded session.

## Local privacy and integrity

- Config, job JSON, and Q&A inputs are size-bounded and versioned.
- Workspace paths cannot traverse outside the selected workspace.
- Reports and pending-question data use private directories, atomic writes, origin-only URL metadata, allowlisted fields, escaped remote text, and SHA-256 integrity manifests.
- Existing non-empty form values are preserved rather than overwritten.

## Supply chain and operations

- The installer accepts only a version tag or full commit SHA and requires the downloaded archive SHA-256 before extraction or execution.
- The CLI no longer downloads and executes a mutable PowerShell script for updates.
- npm is documented as a transparent launcher, not a hidden Python installer.
- CI resolves third-party actions to immutable commit SHAs, runs cross-platform unit checks, Chromium fixtures, dependency audit, type checking, release verification, and package-content checks.

## Product and platform clarity

The display name is **Job Apply Assistant**. The historical package/repository identifier remains for compatibility. The project is independent and is not affiliated with, endorsed by, or sponsored by LinkedIn Corporation. Users remain responsible for platform terms, employer rules, and local law; automation must stop at platform risk signals and before final submission.
''',
}


def _patch_docs() -> None:
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"^# LinkedIn-apply-assistant", "# Job Apply Assistant", text)
        notice = (
            "\n> **Independent project:** Job Apply Assistant is not affiliated with, endorsed by, or sponsored by LinkedIn Corporation. "
            "The historical package identifier is retained only for compatibility.\n"
        )
        if "Independent project:" not in text:
            first_break = text.find("\n")
            text = text[: first_break + 1] + notice + text[first_break + 1 :]
        text = text.replace(
            "irm https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1 | iex",
            "# Download a tagged installer, inspect it, verify its SHA-256, then run it with -ExpectedSha256.\n# Mutable main-branch pipe-to-shell installation is intentionally unsupported.",
        )
        text = text.replace(
            "NPM:\n\n```bash\nnpm install -g linkedin-apply-assistant\n```",
            "Python source or pipx is the supported installation path. The npm artifact is a transparent launcher only and does not install Python dependencies.",
        )
        if "docs/audit-remediation.md" not in text:
            text += "\n## Security remediation\n\nSee [the comprehensive audit remediation](docs/audit-remediation.md).\n"
        readme.write_text(text, encoding="utf-8")

    install_doc = ROOT / "docs" / "install-and-configuration.md"
    if install_doc.exists():
        text = install_doc.read_text(encoding="utf-8")
        text = text.replace(
            "irm https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1 | iex",
            "$script = Join-Path $env:TEMP 'job-apply-assistant-install.ps1'\n"
            "iwr https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1 -OutFile $script\n"
            "# Inspect $script, obtain the tagged archive SHA-256, then run:\n"
            "& $script -Ref v0.1.5 -ExpectedSha256 <verified-sha256>",
        )
        text = text.replace("The npm launcher and PowerShell no-admin installer are the current quick-install paths.", "Source/pipx installation is the supported path. npm remains a transparent compatibility launcher; the PowerShell installer requires a pinned ref and verified SHA-256.")
        install_doc.write_text(text, encoding="utf-8")

    security = ROOT / "SECURITY.md"
    if security.exists():
        text = security.read_text(encoding="utf-8")
        route = "https://github.com/MohammedGhazal09/linkedin-apply-assistant/security/advisories/new"
        if route not in text:
            text = text.replace(
                "Use GitHub private vulnerability reporting for the standalone project when available.",
                f"Report vulnerabilities privately through GitHub Security Advisories: `{route}`.",
            )
        security.write_text(text, encoding="utf-8")

    legal = ROOT / "LEGAL.md"
    if legal.exists():
        text = legal.read_text(encoding="utf-8")
        if "not affiliated with" not in text.lower():
            text = text.replace(
                "LinkedIn-apply-assistant is an experimental local automation package",
                "Job Apply Assistant is an independent, experimental local automation package that is not affiliated with, endorsed by, or sponsored by LinkedIn Corporation and is",
            )
        legal.write_text(text, encoding="utf-8")

    safety = ROOT / "SAFETY.md"
    if safety.exists():
        text = safety.read_text(encoding="utf-8")
        if "explicitly approved origin" not in text:
            text += (
                "\n## Origin trust\n\nCandidate fields and private documents may be written only to a known application-provider HTTPS origin or an origin explicitly approved by the user for that session. URL paths and query strings never establish ATS trust.\n"
            )
        safety.write_text(text, encoding="utf-8")


def _patch_metadata() -> None:
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = text.replace('description = "Local LinkedIn application assistant with user-visible browser workflows"', 'description = "Independent local job-application assistant with visible no-submit browser workflows"')
    text = re.sub(r'  "scrapling>=0\.2\.0",\n', "", text)
    text = text.replace('"playwright>=1.40"', '"playwright>=1.40,<2"')
    text = text.replace('"PyYAML>=6.0"', '"PyYAML>=6.0,<7"')
    text = text.replace('"platformdirs>=4.0"', '"platformdirs>=4.0,<5"')
    if '"mypy>=' not in text:
        text = text.replace('  "ruff>=0.6",\n', '  "ruff>=0.6,<1",\n  "mypy>=1.11,<2",\n  "types-PyYAML>=6.0,<7",\n  "pip-tools>=7.4,<8",\n')
    if "[tool.mypy]" not in text:
        text += '\n[tool.mypy]\npython_version = "3.11"\nfiles = ["src/linkedin_apply_assistant"]\nignore_missing_imports = true\nwarn_unused_ignores = true\ncheck_untyped_defs = true\n'
    pyproject.write_text(text, encoding="utf-8")

    package = ROOT / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data["description"] = "Transparent npm launcher for the independent Python Job Apply Assistant"
    data["engines"] = {"node": ">=20"}
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    if notices.exists():
        text = notices.read_text(encoding="utf-8")
        text = re.sub(r"\n## Scrapling\n.*", "\n", text, flags=re.DOTALL)
        notices.write_text(text, encoding="utf-8")


def apply() -> None:
    for relative, content in FILES.items():
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
    _patch_docs()
    _patch_metadata()


if __name__ == "__main__":
    apply()
