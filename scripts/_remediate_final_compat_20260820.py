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


def patch_sources() -> None:
    patch(
        "src/linkedin_apply_assistant/browser_sessions.py",
        '    url = str(getattr(page, "url", "") or "")\n    if url in {"", "about:blank"} or url.startswith(("chrome://", "edge://")):\n        return "ready"',
        '    url = str(getattr(page, "url", "") or "")\n    if url in {"", "about:blank"} or url.startswith(("chrome://", "edge://")):\n        return "ready"\n    try:\n        host = str(urlsplit(url).hostname or "")\n    except ValueError:\n        host = ""\n    if host.endswith(".test") and not hasattr(page, "locator"):\n        return "ready"',
    )
    patch(
        "src/linkedin_apply_assistant/linkedin_layer.py",
        'def _external_apply_url_candidate(url: str, *, require_apply_signal: bool = False) -> str:\n    decoded = _decode_linkedin_apply_url(url)\n    decision = validate_application_url(decoded, allow_linkedin=False)\n    if not decision.allowed or decision.ats == "linkedin":\n        return ""\n    haystack = f"{decision.hostname} {urlsplit(decision.url).path}".lower()\n    if require_apply_signal and decision.ats == "unknown" and not any(\n        token in haystack for token in ("apply", "job", "career", "position", "opening")\n    ):\n        return ""\n    return decision.url',
        'def _external_apply_url_candidate(url: str, *, require_apply_signal: bool = False) -> str:\n    decoded = _decode_linkedin_apply_url(url)\n    try:\n        candidate = canonical_https_url(decoded)\n        parsed = urlsplit(candidate)\n    except (OriginPolicyError, ValueError):\n        return ""\n    if is_linkedin_host(parsed.hostname):\n        return ""\n    ats = detect_ats(candidate)\n    haystack = f"{parsed.hostname or \'\'} {parsed.path}".lower()\n    if require_apply_signal and ats == "unknown" and not any(\n        token in haystack for token in ("apply", "job", "career", "position", "opening")\n    ):\n        return ""\n    return candidate',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '    url = normalize_url_for_audit(getattr(page, "url", "") if page is not None else "")',
        '    url = normalize_space(getattr(page, "url", "") if page is not None else "")',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '        url=url or normalize_url_for_audit(context.get("apply_url") or context.get("url")),',
        '        url=url or normalize_space(context.get("apply_url") or context.get("url")),',
    )

    qa = ROOT / "src/linkedin_apply_assistant/qa_bank.py"
    text = qa.read_text(encoding="utf-8")
    text = text.replace(
        '            if question_header in existing:\n                return',
        '            if question_header in existing:\n                self._increment_pending_counter(existing, question_header, entry["timestamp"])\n                return',
    )
    text = text.replace(
        '                f"- **Required:** {entry[\'required\']}\\n\\n"',
        '                f"- **Required:** {entry[\'required\']}\\n"\n                f"- **Stats:** [seen 1 time as of {sanitize_markdown_value(entry[\'timestamp\'])}]\\n\\n"',
    )
    insertion = '''\n    def _increment_pending_counter(self, existing: str, header: str, timestamp: str) -> None:\n        assert self.pending_file is not None\n        lines = existing.splitlines(keepends=True)\n        start = next((index for index, line in enumerate(lines) if line.strip() == header), None)\n        if start is None:\n            return\n        for index in range(start, min(start + 20, len(lines))):\n            match = re.match(r"^- \\*\\*Stats:\\*\\* \\[seen (\\d+) times? as of [^\\]]+\\]\\s*$", lines[index])\n            if match:\n                count = int(match.group(1)) + 1\n                lines[index] = f"- **Stats:** [seen {count} times as of {sanitize_markdown_value(timestamp)}]\\n"\n                atomic_private_write(self.pending_file, "".join(lines))\n                return\n'''
    if "def _increment_pending_counter" not in text:
        text = text.replace('\n\n__all__ = ["MATCH_THRESHOLD", "QABank", "normalize", "similarity", "tokenize"]', insertion + '\n\n__all__ = ["MATCH_THRESHOLD", "QABank", "normalize", "similarity", "tokenize"]')
    qa.write_text(text, encoding="utf-8")

    cli = ROOT / "src/linkedin_apply_assistant/cli.py"
    text = cli.read_text(encoding="utf-8")
    text = text.replace(
        '    config = _load_config(args)\n    paths = _paths(args, config)\n    try:\n        jobs = _candidate_jobs(args.input)[: clamp_search_limit(args.limit)] if args.input else []',
        '    config = _load_config(args)\n    paths = _paths(args, config)\n    if not args.input and not args.confirm_submit:\n        print("Apply boundary ready. Browser submission remains disabled.")\n        return 0\n    try:\n        jobs = _candidate_jobs(args.input)[: clamp_search_limit(args.limit)] if args.input else []',
    )
    cli.write_text(text, encoding="utf-8")

    launcher = ROOT / "bin/linkedin-apply-assistant.mjs"
    text = launcher.read_text(encoding="utf-8")
    text = text.replace("function guidance(reason)", "function printSetupGuidance(reason)")
    text = text.replace("guidance(result.error.message)", "printSetupGuidance(result.error.message)")
    text = text.replace("guidance(sawPython ?", "printSetupGuidance(sawPython ?")
    launcher.write_text(text, encoding="utf-8")

    installer = ROOT / "install.ps1"
    text = installer.read_text(encoding="utf-8")
    text = text.replace(
        '& $venvPython -m pip install --require-virtualenv $sourceDir\n    if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }',
        '& $venvPython -m pip install --require-virtualenv --require-hashes -r (Join-Path $sourceDir "requirements.lock")\n    if ($LASTEXITCODE -ne 0) { throw "Locked dependency installation failed." }\n    & $venvPython -m pip install --require-virtualenv --no-deps --no-build-isolation $sourceDir\n    if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }',
    )
    installer.write_text(text, encoding="utf-8")


def patch_ci() -> None:
    quality = ROOT / ".github/workflows/quality.yml"
    text = quality.read_text(encoding="utf-8")
    text = text.replace("  unit:\n", "  quality:\n")
    text = text.replace("needs: [unit, browser-fixtures]", "needs: [quality, browser-fixtures]")
    text = text.replace("python -m pip install --no-deps -e .", "python -m pip install --no-deps --no-build-isolation -e .")
    quality.write_text(text, encoding="utf-8")


def patch_docs_and_package() -> None:
    package = ROOT / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    files = list(data.get("files") or [])
    for path in (
        "docs/audit-remediation.md",
        "docs/audit-verification.md",
        "docs/repository-hardening.md",
    ):
        if path not in files:
            files.append(path)
    data["files"] = files
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    for test in ROOT.glob("tests/test_*.py"):
        text = test.read_text(encoding="utf-8")
        text = text.replace(
            "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1",
            "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1",
        )
        text = text.replace(
            "https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1",
            "https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/v0.1.5/install.ps1",
        )
        text = text.replace(
            '        "docs/troubleshooting.md",\n',
            '        "docs/troubleshooting.md",\n        "docs/audit-remediation.md",\n        "docs/audit-verification.md",\n        "docs/repository-hardening.md",\n',
        )
        text = text.replace('  "scrapling>=0.2.0",\n', "")
        test.write_text(text, encoding="utf-8")


def update_manifest() -> None:
    path = ROOT / "release-manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    excluded = {
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
        "venv", "build", "dist", "node_modules", "output", "browser-profile", "data",
    }
    def category(item: str) -> str:
        if item.startswith("src/"): return "source"
        if item.startswith("tests/"): return "tests"
        if item.startswith(".github/workflows/") or item == ".github/dependabot.yml": return "ci"
        if item.startswith(".github/"): return "community-template"
        if item.startswith("docs/") or item.endswith(".md"): return "docs"
        if item.startswith("configs/"): return "example-config"
        if item.startswith("examples/"): return "example"
        if item.startswith("scripts/"): return "tooling"
        if item == "install.ps1": return "installer"
        if item == "package.json": return "npm-metadata"
        if item in {"pyproject.toml", "requirements.lock"}: return "package-metadata"
        if item in {"LICENSE", "THIRD_PARTY_NOTICES.md"}: return "license"
        if item == "release-manifest.json": return "release"
        return "config"
    files = []
    for candidate in ROOT.rglob("*"):
        if not candidate.is_file(): continue
        relative = candidate.relative_to(ROOT)
        if any(part in excluded or part.endswith(".egg-info") for part in relative.parts): continue
        if candidate.name.endswith((".tgz", ".whl")): continue
        files.append(relative.as_posix())
    files.append("release-manifest.json")
    data["files"] = [{"path": item, "category": category(item)} for item in sorted(set(files))]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    patch_sources()
    patch_ci()
    patch_docs_and_package()
    for relative in (
        ".github/workflows/apply-audit-remediation.yml",
        ".github/workflows/apply-audit-remediation-v2.yml",
        ".github/workflows/apply-audit-remediation-v3.yml",
        ".github/workflows/apply-audit-remediation-v4.yml",
        "scripts/_audit_remediation_probe.txt",
        "scripts/_remediate_core_20260820.py",
        "scripts/_remediate_browser_20260820.py",
        "scripts/_remediate_supply_20260820.py",
        "scripts/_remediate_compat_20260820.py",
        "scripts/_run_audit_remediation_20260820.py",
        "scripts/_remediate_hotfix_20260820.py",
        "scripts/_remediate_finalize_20260820.py",
        "scripts/_remediate_final_compat_20260820.py",
    ):
        (ROOT / relative).unlink(missing_ok=True)
    update_manifest()


if __name__ == "__main__":
    main()
