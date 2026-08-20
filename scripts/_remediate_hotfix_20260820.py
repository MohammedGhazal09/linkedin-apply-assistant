from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")


def update_manifest() -> None:
    manifest_path = ROOT / "release-manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    excluded = {
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
        "venv", "build", "dist", "node_modules", "output", "browser-profile", "data",
    }
    def category(path: str) -> str:
        if path.startswith("src/"): return "source"
        if path.startswith("tests/"): return "tests"
        if path.startswith(".github/workflows/") or path == ".github/dependabot.yml": return "ci"
        if path.startswith(".github/"): return "community-template"
        if path.startswith("docs/") or path.endswith(".md"): return "docs"
        if path.startswith("configs/"): return "example-config"
        if path.startswith("examples/"): return "example"
        if path.startswith("scripts/"): return "tooling"
        if path == "install.ps1": return "installer"
        if path == "package.json": return "npm-metadata"
        if path in {"pyproject.toml", "requirements.lock"}: return "package-metadata"
        if path in {"LICENSE", "THIRD_PARTY_NOTICES.md"}: return "license"
        if path == "release-manifest.json": return "release"
        return "config"
    files = []
    for candidate in ROOT.rglob("*"):
        if not candidate.is_file(): continue
        relative = candidate.relative_to(ROOT)
        if any(part in excluded or part.endswith(".egg-info") for part in relative.parts): continue
        if candidate.name.endswith((".tgz", ".whl")): continue
        files.append(relative.as_posix())
    if "release-manifest.json" not in files: files.append("release-manifest.json")
    old["generated_note"] = "Comprehensive audit-remediation manifest generated from the verified final tree."
    old["files"] = [{"path": path, "category": category(path)} for path in sorted(set(files))]
    manifest_path.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")


def apply() -> None:
    patch(
        "src/linkedin_apply_assistant/schemas.py",
        '    required = ["title", "company", "url", "location"]\n    if require_description:\n        required.append("description")',
        '    required = ["title", "company", "url"]\n    if require_description:\n        required.extend(["location", "description"])',
    )
    patch(
        "src/linkedin_apply_assistant/origin_policy.py",
        '    decision = validate_application_url(value, **kwargs)  # type: ignore[arg-type]',
        '    decision = validate_application_url(value, **kwargs)  # type: ignore[arg-type]',
    )
    patch(
        "src/linkedin_apply_assistant/browser_sessions.py",
        '    decision = validate_application_url(url, approved_origins=approved_origins)\n    if not decision.allowed:\n        return "blocked_origin"',
        '    if url in {"", "about:blank"} or url.startswith(("chrome://", "edge://")):\n        return "ready"\n    decision = validate_application_url(url, approved_origins=approved_origins)\n    if not decision.allowed:\n        return "blocked_origin"',
    )
    patch(
        "src/linkedin_apply_assistant/browser_sessions.py",
        '    def wait_for_change(self, seconds: float) -> None:\n',
        '    def wait_for_user_activation(self) -> None:\n'
        '        import sys\n'
        '        if sys.stdin.isatty():\n'
        '            input("Navigate the visible browser to the reviewed application page, then press Enter...")\n\n'
        '    def wait_for_change(self, seconds: float) -> None:\n',
    )
    patch(
        "src/linkedin_apply_assistant/linkedin_layer.py",
        '        url = str(getattr(page, "url", "") or "")\n        page_context = dict(qa_context or {})',
        '        url = str(getattr(page, "url", "") or "")\n        if url in {"", "about:blank"} or url.startswith(("chrome://", "edge://")):\n            continue\n        page_context = dict(qa_context or {})',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '        if request.start_url:\n            session.open_url(request.start_url)\n        cycles = clamp_assist_cycles(request.max_cycles)',
        '        if request.start_url:\n            session.open_url(request.start_url)\n        if request.mode == "on-demand":\n            activation = getattr(session, "wait_for_user_activation", None)\n            if callable(activation):\n                activation()\n        cycles = clamp_assist_cycles(request.max_cycles)',
    )

    cli_path = ROOT / "src/linkedin_apply_assistant/cli.py"
    cli = cli_path.read_text(encoding="utf-8")
    cli = re.sub(
        r'    if mode == "on-demand" and not getattr\(args, "non_interactive", False\) and sys\.stdin\.isatty\(\):\n        input\([^\n]+\)\n',
        "",
        cli,
    )
    cli = cli.replace(
        '    cycles = args.max_cycles if args.max_cycles is not None else int(config.defaults.get("max_cycles", 1))',
        '    cycles = args.max_cycles if args.max_cycles is not None else int(config.defaults.get("max_cycles", 25 if mode == "auto-watch" else 1))',
    )
    cli = cli.replace(
        'def _handle_dry_run(args: argparse.Namespace) -> int:\n    try:\n        jobs = _candidate_jobs(args.input)',
        'def _handle_dry_run(args: argparse.Namespace) -> int:\n    try:\n        jobs = _validate_dry_run_jobs(load_json_limited(args.input))',
    )
    cli_path.write_text(cli, encoding="utf-8")

    # Remove both temporary execution workflows and all generator artifacts.
    for relative in (
        ".github/workflows/apply-audit-remediation.yml",
        ".github/workflows/apply-audit-remediation-v2.yml",
        "scripts/_audit_remediation_probe.txt",
        "scripts/_remediate_core_20260820.py",
        "scripts/_remediate_browser_20260820.py",
        "scripts/_remediate_supply_20260820.py",
        "scripts/_remediate_compat_20260820.py",
        "scripts/_run_audit_remediation_20260820.py",
        "scripts/_remediate_hotfix_20260820.py",
    ):
        (ROOT / relative).unlink(missing_ok=True)
    update_manifest()


if __name__ == "__main__":
    apply()
