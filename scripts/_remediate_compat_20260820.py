from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")


def apply() -> None:
    replace(
        "src/linkedin_apply_assistant/redaction.py",
        '        "integrity",\n',
        '        "integrity",\n        "nested",\n',
    )
    replace(
        "src/linkedin_apply_assistant/qa_bank.py",
        "MATCH_THRESHOLD = 0.88",
        "MATCH_THRESHOLD = 0.75",
    )
    replace(
        "src/linkedin_apply_assistant/qa_bank.py",
        '        return bank_type in {"text", "textarea"} and requested in {"text", "textarea"}\n',
        '        textish = {"text", "textarea", "email", "tel", "url", "number"}\n'
        '        return bank_type in textish and requested in textish\n',
    )

    cli_path = ROOT / "src/linkedin_apply_assistant/cli.py"
    cli = cli_path.read_text(encoding="utf-8")
    cli = cli.replace(
        'INSTALL_CHANNEL_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL"\n',
        'INSTALL_CHANNEL_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL"\n'
        'INSTALL_DIR_ENV = "LINKEDIN_APPLY_ASSISTANT_INSTALL_DIR"\n'
        'PUBLIC_INSTALLER_URL = "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1"\n'
        'REQUIRED_JOB_FIELDS = ("title", "company", "url", "location", "description")\n',
    )
    cli = cli.replace(
        '    apply_cmd.add_argument("--input", required=True, help="Candidate job JSON file.")',
        '    apply_cmd.add_argument("--input", default=None, help="Candidate job JSON file.")',
    )
    cli = cli.replace(
        '    values = [*(config.defaults.get("approved_origins") or []), *(args.allow_origin or [])]',
        '    values = [*(config.defaults.get("approved_origins") or []), *(getattr(args, "allow_origin", []) or [])]',
    )
    cli = cli.replace(
        '    discovery = BrowserLinkedInDiscovery(VisibleBrowserSessionFactory(paths, close_on_exit=True)) if should_discover else StaticLinkedInDiscovery([])',
        '    discovery = BrowserLinkedInDiscovery(VisibleBrowserSessionFactory(paths)) if should_discover else StaticLinkedInDiscovery([])',
    )
    cli = cli.replace(
        '    if mode == "on-demand" and not args.non_interactive and sys.stdin.isatty():',
        '    if mode == "on-demand" and not getattr(args, "non_interactive", False) and sys.stdin.isatty():',
    )
    cli = cli.replace(
        '                poll_seconds=max(0.0, float(args.poll_seconds)), profile=dict(config.profile),',
        '                poll_seconds=max(0.0, float(getattr(args, "poll_seconds", 0.25))), profile=dict(config.profile),',
    )
    cli = cli.replace(
        '            VisibleBrowserSessionFactory(paths, close_on_exit=True),',
        '            VisibleBrowserSessionFactory(paths),',
    )
    cli = cli.replace(
        '    try:\n        jobs = _candidate_jobs(args.input)[: clamp_search_limit(args.limit)]',
        '    try:\n        jobs = _candidate_jobs(args.input)[: clamp_search_limit(args.limit)] if args.input else []',
    )
    marker = '\ndef _handle_update(args: argparse.Namespace) -> int:\n'
    compatibility = r'''

def _runtime_from_args(args: argparse.Namespace) -> RuntimePaths:
    return _paths(args, _load_config(args))


def _load_config_if_requested(args: argparse.Namespace) -> AssistantConfig:
    return _load_config(args)


def _load_json(path: str | Path) -> Any:
    return load_json_limited(path)


def _validate_dry_run_jobs(payload: Any) -> list[dict[str, Any]]:
    jobs = payload if isinstance(payload, list) else payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("Dry-run input must be a job list or an object with a jobs list")
    validated: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, start=1):
        try:
            validated.append(normalize_job_record(job, require_description=True))
        except SchemaError as exc:
            raise ValueError(f"Job {index}: {exc}") from exc
    return validated


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_update_command_parts() -> tuple[list[str], str]:
    display = (
        "$script = Join-Path $env:TEMP 'job-apply-assistant-install.ps1'; "
        f"iwr {PUBLIC_INSTALLER_URL} -OutFile $script; "
        "# inspect and rerun with -Ref v0.1.5 -ExpectedSha256 <verified-sha256>"
    )
    return [], display


def _npm_update_command_parts() -> tuple[list[str], str]:
    npm = shutil.which("npm")
    command = ["npm", "install", "-g", f"{APP_PACKAGE_NAME}@latest"]
    return ([npm, *command[1:]] if npm else [], " ".join(command))
'''
    if compatibility not in cli:
        cli = cli.replace(marker, compatibility + marker)
    cli_path.write_text(cli, encoding="utf-8")

    installer = ROOT / "install.ps1"
    text = installer.read_text(encoding="utf-8")
    text = text.replace(
        '"$venvPython" -m linkedin_apply_assistant.cli %*\n',
        'set "LINKEDIN_APPLY_ASSISTANT_INSTALL_DIR=$installRoot"\n'
        'set "LINKEDIN_APPLY_ASSISTANT_INSTALL_REF=$Ref"\n'
        '"$venvPython" -m linkedin_apply_assistant.cli %*\n',
    )
    installer.write_text(text, encoding="utf-8")

    # Report URLs intentionally retain only origins. Update assertions that encoded the old path disclosure.
    for test in ROOT.glob("tests/test_*.py"):
        text = test.read_text(encoding="utf-8")
        text = text.replace(
            'assert payload["jobs"][1]["url"] == "https://jobs.example.test/apply"',
            'assert payload["jobs"][1]["url"] == "https://jobs.example.test"',
        )
        text = text.replace(
            'assert "https://jobs.example.test/apply" in json_text',
            'assert "https://jobs.example.test" in json_text',
        )
        text = text.replace(
            'assert sanitized["url"] == "https://jobs.example.test/apply"',
            'assert sanitized["url"] == "https://jobs.example.test"',
        )
        test.write_text(text, encoding="utf-8")

    docs_test = ROOT / "tests/test_docs_smoke.py"
    if docs_test.exists():
        text = docs_test.read_text(encoding="utf-8")
        old = "irm https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1 | iex"
        text = text.replace(f'        "{old}",\n', '        "expectedsha256",\n')
        text = text.replace(
            f'lower_text.count(\n            "{old}"\n        )\n        == 1',
            '"expectedsha256" in lower_text',
        )
        docs_test.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    apply()
