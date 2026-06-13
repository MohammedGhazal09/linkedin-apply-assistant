"""Command-line boundary for the standalone assistant."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import APP_PACKAGE_NAME, __version__
from .apply_reports import RuntimeReportSink
from .ats_handlers import DisabledSubmissionPolicy
from .browser_sessions import PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND, VisibleBrowserSessionFactory
from .config import AssistantConfig, load_config
from .contracts import AssistRequest, SearchRequest
from .linkedin_layer import (
    BrowserLinkedInDiscovery,
    CurrentSurfaceDetector,
    CurrentSurfaceFillAdapter,
    StaticLinkedInDiscovery,
)
from .paths import resolve_runtime_paths
from .qa_bank import QABank
from .safety import BROWSER_PROFILE_WARNING, disabled_submit_audit_payload
from .workflows import compact_assist_feedback, run_assist_workflow, run_search_workflow


REQUIRED_JOB_FIELDS = ("title", "company", "url", "location", "description")
CONFIG_CHECK_COMMAND = "linkedin-apply-assistant config check"
CONFIG_EXAMPLE_PATH = "configs/config.example.yml"
QA_BANK_EXAMPLE_PATH = "configs/qa_bank.example.yml"
PUBLIC_INSTALLER_URL = (
    "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1"
)
INSTALL_CHANNEL_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL"
INSTALL_DIR_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_DIR"
NO_SUBMIT_HELP = (
    "Safety: public workflows are no-submit by default; assist is fill-only and "
    "browser submission remains disabled in apply."
)


class CliError(Exception):
    """User-facing CLI error."""


def _common_default(suppress_defaults: bool) -> str | None:
    return argparse.SUPPRESS if suppress_defaults else None


def _add_common_options(
    parser: argparse.ArgumentParser, *, suppress_defaults: bool = False
) -> None:
    default = _common_default(suppress_defaults)
    parser.add_argument(
        "--workspace",
        default=default,
        help="Use a local workspace for config, data, browser profile, output, and reports.",
    )
    parser.add_argument(
        "--config",
        default=default,
        help="Path to an assistant YAML config file.",
    )
    parser.add_argument(
        "--qa-bank",
        default=default,
        help="Path to a Q&A bank YAML file.",
    )
    parser.add_argument(
        "--browser-profile",
        default=default,
        help="Path to the visible-browser profile directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=default,
        help="Path for local command outputs.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="Print additional command-boundary details.",
    )


def build_parser() -> argparse.ArgumentParser:
    root_common = argparse.ArgumentParser(add_help=False)
    _add_common_options(root_common)
    subcommand_common = argparse.ArgumentParser(add_help=False)
    _add_common_options(subcommand_common, suppress_defaults=True)
    formatter = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        prog="linkedin-apply-assistant",
        parents=[root_common],
        formatter_class=formatter,
        description=(
            "Local, user-visible LinkedIn application assistant for search-only, "
            "assistive fill-only, approval-gated apply, dry-run, and report generation."
        ),
        epilog=f"""First run:
  {CONFIG_CHECK_COMMAND}
  python -m playwright install chromium

Common workflows:
  linkedin-apply-assistant search --query "python" --limit 5
  linkedin-apply-assistant assist --mode on-demand
  linkedin-apply-assistant dry-run --input examples/dry_run_input.example.json

Outputs use the resolved output directory and reports are written under its reports folder.
{NO_SUBMIT_HELP}
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    config = subparsers.add_parser(
        "config",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Inspect first-run paths and setup gaps without writing files.",
        description="Read-only configuration diagnostics for first-run setup.",
        epilog=f"""Examples:
  {CONFIG_CHECK_COMMAND}
  linkedin-apply-assistant --workspace .assistant-workspace config check

The diagnostic resolves config, Q&A bank, browser profile, output, reports, data, and cache paths.
It creates no files and no directories.
""",
    )
    config_subparsers = config.add_subparsers(dest="config_command")
    config_check = config_subparsers.add_parser(
        "check",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Report resolved paths and setup guidance without writing files.",
        description="Check first-run paths and setup gaps without creating or overwriting files.",
        epilog=f"""Examples:
  {CONFIG_CHECK_COMMAND}
  linkedin-apply-assistant config check --workspace .assistant-workspace

Status labels: ok, missing, warning.
No files or directories are created by this command.
""",
    )
    config_check.set_defaults(handler=_handle_config_check)

    search = subparsers.add_parser(
        "search",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Search-only boundary for collecting candidate jobs.",
        description="Search LinkedIn jobs and write local search reports without submitting applications.",
        epilog=f"""Examples:
  linkedin-apply-assistant search --query "python" --location "Remote" --limit 5
  linkedin-apply-assistant search --workspace .assistant-workspace --search-url "https://www.linkedin.com/jobs/search/" --limit 10 --verbose

Reports are written under the resolved reports directory.
Run `{CONFIG_CHECK_COMMAND}` to inspect paths before browser workflows.
{NO_SUBMIT_HELP}
""",
    )
    search.add_argument("--query", default=None, help="Search query text.")
    search.add_argument("--location", default=None, help="Search location text.")
    search.add_argument("--limit", type=int, default=10, help="Maximum jobs to inspect.")
    search.add_argument("--search-url", default=None, help="Existing LinkedIn jobs search URL.")
    search.set_defaults(handler=_handle_search)

    assist = subparsers.add_parser(
        "assist",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Assistive fill-only boundary where the user drives the visible browser.",
        description="Open a visible browser session and fill detected application forms without submitting.",
        epilog=f"""Examples:
  linkedin-apply-assistant assist --mode on-demand
  linkedin-apply-assistant assist --workspace .assistant-workspace --browser-profile .browser-profile --verbose

Install browser support with: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND}
Reports are written under the resolved reports directory.
{NO_SUBMIT_HELP}
""",
    )
    assist.add_argument("--start-url", default=None, help="Optional first page to open.")
    assist.add_argument(
        "--mode",
        choices=("auto-watch", "on-demand"),
        default="auto-watch",
        help="Assist mode for visible-browser filling.",
    )
    assist.add_argument(
        "--max-cycles", type=int, default=1, help="Maximum detected surfaces to inspect."
    )
    assist.set_defaults(handler=_handle_assist)

    apply_cmd = subparsers.add_parser(
        "apply",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Apply-with-approval boundary; submissions require explicit confirmation.",
        description="Prepare local apply reports while browser submission remains disabled.",
        epilog=f"""Examples:
  linkedin-apply-assistant apply --input candidates.json --limit 3
  linkedin-apply-assistant apply --workspace .assistant-workspace --input candidates.json --verbose

Current package behavior is prepare-only. Browser submission remains disabled.
Reports are written under the resolved reports directory.
{NO_SUBMIT_HELP}
""",
    )
    apply_cmd.add_argument("--input", default=None, help="Path to candidate jobs JSON.")
    apply_cmd.add_argument("--limit", type=int, default=10, help="Maximum jobs to prepare.")
    apply_cmd.add_argument(
        "--confirm-submit",
        action="store_true",
        help=(
            "Guarded future option: every submission still requires explicit "
            "per-submission confirmation and Phase 16 safety guardrails."
        ),
    )
    apply_cmd.set_defaults(handler=_handle_apply)

    dry_run = subparsers.add_parser(
        "dry-run",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Validate local job input without browser submission.",
        description="Validate local JSON job input without config, Q&A bank, Playwright, or a browser profile.",
        epilog="""Example:
  linkedin-apply-assistant dry-run --input examples/dry_run_input.example.json

This command is browser-free and does not require config or Q&A setup.
""",
    )
    dry_run.add_argument("--input", required=True, help="Path to dry-run JSON input.")
    dry_run.set_defaults(handler=_handle_dry_run)

    report = subparsers.add_parser(
        "report",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Read a local report JSON file and print a simple summary.",
        description="Summarize a local report JSON file without config, Q&A bank, Playwright, or a browser profile.",
        epilog="""Example:
  linkedin-apply-assistant report output/reports/search_example.json

This command is browser-free and reads an existing local report file.
""",
    )
    report.add_argument("report_json", help="Path to the report JSON file.")
    report.set_defaults(handler=_handle_report)

    update = subparsers.add_parser(
        "update",
        parents=[subcommand_common],
        formatter_class=formatter,
        help="Update the installed package through npm or the PowerShell installer.",
        description=(
            "Update linkedin-apply-assistant through the detected install channel. "
            "npm installs use npm; PowerShell installs rerun the public installer."
        ),
        epilog=f"""Examples:
  linkedin-apply-assistant update
  linkedin-apply-assistant update --check
  linkedin-apply-assistant update --method npm
  linkedin-apply-assistant update --method powershell

NPM update command:
  npm install -g {APP_PACKAGE_NAME}@latest

PowerShell update command:
  irm {PUBLIC_INSTALLER_URL} | iex
""",
    )
    update.add_argument(
        "--method",
        choices=("auto", "npm", "powershell"),
        default="auto",
        help="Choose the update mechanism. Auto uses the detected install channel.",
    )
    update.add_argument(
        "--check",
        action="store_true",
        help="Show the selected update command without running it.",
    )
    update.set_defaults(handler=_handle_update)

    return parser


def _runtime_from_args(args: argparse.Namespace):
    return resolve_runtime_paths(
        workspace=args.workspace,
        config=args.config,
        qa_bank=args.qa_bank,
        browser_profile=args.browser_profile,
        output_dir=args.output_dir,
    )


def _with_config_check_hint(message: str) -> str:
    return f"{message}\nTry: {CONFIG_CHECK_COMMAND}"


def _print_error(message: str, *hints: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    for hint in hints:
        print(hint, file=sys.stderr)


def _path_status(path: Path, *, expected: str) -> str:
    if not path.exists():
        return "missing" if expected == "file" else "warning"
    if expected == "file" and not path.is_file():
        return "warning"
    if expected == "directory" and not path.is_dir():
        return "warning"
    return "ok"


def _diagnostic_rows(paths: Any) -> list[tuple[str, str, Path, str]]:
    return [
        (
            "config file",
            _path_status(paths.config_file, expected="file"),
            paths.config_file,
            f"Copy {CONFIG_EXAMPLE_PATH} and edit it before browser workflows if needed.",
        ),
        (
            "Q&A bank",
            _path_status(paths.qa_bank_file, expected="file"),
            paths.qa_bank_file,
            (
                f"Copy {QA_BANK_EXAMPLE_PATH} and answer truthfully; missing answers are "
                "captured as pending questions during assist workflows."
            ),
        ),
        (
            "browser profile",
            _path_status(paths.browser_profile_dir, expected="directory"),
            paths.browser_profile_dir,
            "Created only by visible-browser workflows; override with --browser-profile <path>.",
        ),
        (
            "output directory",
            _path_status(paths.output_dir, expected="directory"),
            paths.output_dir,
            "Created when commands write local outputs.",
        ),
        (
            "reports directory",
            _path_status(paths.reports_dir, expected="directory"),
            paths.reports_dir,
            "Created when commands write report JSON files.",
        ),
        (
            "data directory",
            _path_status(paths.data_dir, expected="directory"),
            paths.data_dir,
            "Used for local assistant data such as pending questions.",
        ),
        (
            "cache directory",
            _path_status(paths.cache_dir, expected="directory"),
            paths.cache_dir,
            "Used for local cache data when workflows need it.",
        ),
    ]


def _handle_config_check(args: argparse.Namespace) -> int:
    paths = _runtime_from_args(args)
    print("Config diagnostics")
    print("No files or directories were created.")
    print()
    print(f"{'status':<8} {'item':<18} path")
    print(f"{'-' * 8} {'-' * 18} {'-' * 4}")
    for label, status, path, detail in _diagnostic_rows(paths):
        print(f"{status:<8} {label:<18} {path}")
        print(f"{'':<8} {'':<18} {detail}")
    print()
    print(f"Try: {PLAYWRIGHT_CHROMIUM_INSTALL_COMMAND} before visible-browser workflows.")
    print(f"Try: {CONFIG_CHECK_COMMAND} after changing --workspace or path flags.")
    return 0


def _qa_bank_setup_warning(paths: Any, bank: QABank) -> str | None:
    pairs = bank.data.get("qa_pairs")
    if not paths.qa_bank_file.exists():
        return (
            f"Warning: Q&A bank is missing: {paths.qa_bank_file}\n"
            f"Copy {QA_BANK_EXAMPLE_PATH} and answer truthfully before filling forms."
        )
    if not isinstance(pairs, list) or not pairs:
        return (
            f"Warning: Q&A bank has no qa_pairs: {paths.qa_bank_file}\n"
            f"Use {QA_BANK_EXAMPLE_PATH} as the format and answer truthfully."
        )
    return None


def _load_config_if_requested(args: argparse.Namespace) -> AssistantConfig:
    if args.config:
        try:
            return load_config(args.config, workspace=args.workspace)
        except FileNotFoundError as exc:
            raise CliError(_with_config_check_hint(f"Config file not found: {exc}")) from exc
        except ValueError as exc:
            raise CliError(_with_config_check_hint(f"Invalid config: {exc}")) from exc
    return AssistantConfig()


def _handle_search(args: argparse.Namespace) -> int:
    config = _load_config_if_requested(args)
    paths = _runtime_from_args(args)
    should_discover = args.limit > 0 and bool(args.search_url or args.query or args.location)
    discovery = (
        BrowserLinkedInDiscovery(VisibleBrowserSessionFactory(paths, close_on_exit=True))
        if should_discover
        else StaticLinkedInDiscovery([])
    )
    try:
        result = run_search_workflow(
            SearchRequest(
                limit=args.limit,
                search_url=args.search_url,
                query=args.query,
                location=args.location,
                profile=dict(config.profile),
                paths=paths,
            ),
            discovery,
            RuntimeReportSink(paths=paths),
            DisabledSubmissionPolicy(),
        )
    except RuntimeError as exc:
        raise CliError(str(exc)) from exc

    print("Search complete.")
    print(f"Requested limit: {args.limit}")
    print(f"Effective limit: {result.summary.get('effective_limit', args.limit)}")
    print(f"Jobs recorded: {len(result.jobs)}")
    print(f"Search URL: {result.search_url}")
    for artifact in result.reports:
        print(f"{artifact.kind} report: {artifact.path}")
    if args.verbose:
        print(f"Output directory: {paths.output_dir}")
    return 0


def _handle_assist(args: argparse.Namespace) -> int:
    config = _load_config_if_requested(args)
    paths = _runtime_from_args(args)
    try:
        bank = QABank.from_runtime_paths(paths, profile=dict(config.profile))
    except ValueError as exc:
        raise CliError(_with_config_check_hint(f"Invalid Q&A bank: {exc}")) from exc
    qa_warning = _qa_bank_setup_warning(paths, bank)
    if qa_warning:
        print(qa_warning)
    print(BROWSER_PROFILE_WARNING)
    try:
        result = run_assist_workflow(
            AssistRequest(
                start_url=args.start_url,
                mode=args.mode,
                max_cycles=args.max_cycles,
                profile=dict(config.profile),
                documents=dict(config.documents),
                paths=paths,
            ),
            VisibleBrowserSessionFactory(paths),
            CurrentSurfaceDetector(profile=dict(config.profile), bank=bank),
            CurrentSurfaceFillAdapter(),
            RuntimeReportSink(paths=paths),
            DisabledSubmissionPolicy(),
            bank,
        )
    except RuntimeError as exc:
        raise CliError(str(exc)) from exc
    print("Assist complete.")
    print(f"Mode: {result.summary.get('mode', args.mode)}")
    print(f"Events: {result.summary.get('events', len(result.events))}")
    print(f"Filled: {result.summary.get('filled', 0)}")
    print(f"Blocked: {result.summary.get('blocked', 0)}")
    print(f"Submitted: {result.summary.get('submitted', 0)}")
    for event in result.events:
        print(compact_assist_feedback(event))
    for artifact in result.reports:
        print(f"{artifact.kind} report: {artifact.path}")
    if args.verbose:
        print(f"Browser profile directory: {paths.browser_profile_dir}")
    return 0


def _handle_apply(args: argparse.Namespace) -> int:
    _load_config_if_requested(args)
    paths = _runtime_from_args(args)
    sink = RuntimeReportSink(paths=paths)
    print("Apply boundary ready. Submissions require explicit approval and confirmation.")
    print("Browser submission is disabled in this package boundary.")
    if args.input:
        print(f"Input: {args.input}")
    print(f"Limit: {args.limit}")
    if args.confirm_submit:
        print("Confirmation flag noted; browser submission remains disabled in this boundary.")
    if args.confirm_submit or args.input:
        confirmation_state = "flagged_but_disabled" if args.confirm_submit else "input_boundary"
        report = disabled_submit_audit_payload(
            command="apply",
            action="submit",
            context={},
            confirmation_state=confirmation_state,
        )
        report["summary"]["requested_limit"] = args.limit
        report["summary"]["input_provided"] = bool(args.input)
        artifacts = sink.write("apply", report)
        for artifact in artifacts:
            print(f"{artifact.kind} report: {artifact.path}")
    if args.verbose:
        print(f"Reports directory: {paths.reports_dir}")
    return 0


def _load_json(path: str | Path) -> Any:
    json_path = Path(path).expanduser()
    if not json_path.exists():
        raise ValueError(f"JSON file not found: {json_path}")
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {json_path}: {exc.msg}") from exc


def _validate_dry_run_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs = payload["jobs"]
    else:
        raise ValueError("Dry-run input must be a job list or an object with a jobs list")

    validated: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise ValueError(f"Job {index} must be an object")
        missing = [field for field in REQUIRED_JOB_FIELDS if not job.get(field)]
        if missing:
            raise ValueError(f"Job {index} missing required field(s): {', '.join(missing)}")
        validated.append(job)
    return validated


def _handle_dry_run(args: argparse.Namespace) -> int:
    try:
        payload = _load_json(args.input)
        jobs = _validate_dry_run_jobs(payload)
    except ValueError as exc:
        _print_error(str(exc), "Try: check the --input path and JSON format.")
        return 2
    print(f"Dry run input valid: {len(jobs)} job(s)")
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    try:
        payload = _load_json(args.report_json)
    except ValueError as exc:
        _print_error(str(exc), "Try: pass a local report JSON path from the reports directory.")
        return 2

    if isinstance(payload, dict):
        summary = payload.get("summary")
        jobs = payload.get("jobs")
        events = payload.get("events")
        print("Report summary:")
        if isinstance(summary, dict):
            for key in sorted(summary):
                print(f"{key}: {summary[key]}")
        if isinstance(jobs, list):
            print(f"jobs: {len(jobs)}")
        if isinstance(events, list):
            print(f"events: {len(events)}")
        if (
            not isinstance(summary, dict)
            and not isinstance(jobs, list)
            and not isinstance(events, list)
        ):
            print(f"object keys: {len(payload)}")
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

    npm = shutil.which("npm")
    if npm:
        try:
            result = subprocess.run(
                [npm, "root", "-g"],
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result and result.returncode == 0:
            package_root = Path(result.stdout.strip()) / APP_PACKAGE_NAME / "package.json"
            if package_root.exists():
                return "npm"

    if os.name == "nt":
        return "powershell"
    return "npm"


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_update_command_parts() -> tuple[list[str], str]:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        return [], f"irm {PUBLIC_INSTALLER_URL} | iex"

    install_dir = os.environ.get(INSTALL_DIR_ENV, "").strip()
    command = (
        "$script = Join-Path $env:TEMP 'linkedin-apply-assistant-install.ps1'; "
        f"iwr {PUBLIC_INSTALLER_URL} -OutFile $script; "
        "& $script -Update"
    )
    if install_dir:
        command = f"{command} -InstallDir {_powershell_quote(install_dir)}"
    return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], command


def _npm_update_command_parts() -> tuple[list[str], str]:
    npm = shutil.which("npm")
    command = ["npm", "install", "-g", f"{APP_PACKAGE_NAME}@latest"]
    display = " ".join(command)
    return ([npm, *command[1:]] if npm else [], display)


def _handle_update(args: argparse.Namespace) -> int:
    method = _detect_update_method(args.method)
    if method == "npm":
        command, display = _npm_update_command_parts()
    else:
        command, display = _powershell_update_command_parts()

    print(f"Current version: {__version__}")
    print(f"Update method: {method}")
    print(f"Update command: {display}")

    if args.check:
        return 0

    if not command:
        _print_error(
            f"{method} updater is not available on PATH.",
            f"Run manually: {display}",
        )
        return 2

    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        _print_error(
            f"Update command failed with exit code {result.returncode}.",
            f"Run manually: {display}",
        )
        return int(result.returncode or 1)

    print("Update complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        print()
        print(f"Try: {CONFIG_CHECK_COMMAND}")
        return 0
    if args.command == "config" and args.config_command is None:
        args.config_command = "check"
        args.handler = _handle_config_check
    handler = getattr(args, "handler")
    try:
        return int(handler(args))
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
