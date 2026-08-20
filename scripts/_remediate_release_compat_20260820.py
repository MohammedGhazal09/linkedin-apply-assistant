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


def patch_source_contracts() -> None:
    patch(
        "src/linkedin_apply_assistant/safety.py",
        "from urllib.parse import urlsplit, urlunsplit",
        "from urllib.parse import urlsplit",
    )
    patch(
        "src/linkedin_apply_assistant/safety.py",
        "    is_linkedin_host,\n",
        "",
    )
    patch(
        "src/linkedin_apply_assistant/browser_sessions.py",
        "import re\n",
        "",
    )
    patch(
        "src/linkedin_apply_assistant/cli.py",
        "import json\n",
        "",
    )
    patch(
        "src/linkedin_apply_assistant/cli.py",
        '    except (FileNotFoundError, SchemaError, ValueError) as exc:\n        raise CliError(f"Invalid config: {exc}\\nTry: {CONFIG_CHECK_COMMAND}") from exc',
        '    except FileNotFoundError as exc:\n        raise CliError(f"Config file not found: {exc}\\nTry: {CONFIG_CHECK_COMMAND}") from exc\n    except (SchemaError, ValueError) as exc:\n        raise CliError(f"Invalid config: {exc}\\nTry: {CONFIG_CHECK_COMMAND}") from exc',
    )
    patch(
        "src/linkedin_apply_assistant/cli.py",
        'def _bank(paths: RuntimePaths, config: AssistantConfig) -> QABank:\n',
        'def _qa_bank_setup_warning(paths: RuntimePaths, bank: QABank) -> str | None:\n'
        '    pairs = bank.data.get("qa_pairs")\n'
        '    if not paths.qa_bank_file.exists():\n'
        '        return f"Warning: Q&A bank is missing: {paths.qa_bank_file}\\nCopy {QA_BANK_EXAMPLE_PATH} and answer truthfully before filling forms."\n'
        '    if not isinstance(pairs, list) or not pairs:\n'
        '        return f"Warning: Q&A bank has no qa_pairs: {paths.qa_bank_file}\\nUse {QA_BANK_EXAMPLE_PATH} and answer truthfully."\n'
        '    return None\n\n\n'
        'def _bank(paths: RuntimePaths, config: AssistantConfig) -> QABank:\n',
    )
    patch(
        "src/linkedin_apply_assistant/cli.py",
        '    bank = _bank(paths, config)\n    mode = args.mode or str(config.defaults.get("mode", "auto-watch"))',
        '    bank = _bank(paths, config)\n    warning = _qa_bank_setup_warning(paths, bank)\n    if warning:\n        print(warning)\n    mode = args.mode or str(config.defaults.get("mode", "auto-watch"))',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '    if request.mode not in {"auto-watch", "on-demand"}:\n        raise ValueError("assist mode must be auto-watch or on-demand")\n    run_id = uuid4().hex',
        '    mode = "auto-watch" if request.mode == "auto" else request.mode\n    if mode not in {"auto-watch", "on-demand"}:\n        raise ValueError("assist mode must be auto-watch or on-demand")\n    run_id = uuid4().hex',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '        if request.mode == "on-demand":',
        '        if mode == "on-demand":',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '                if request.mode == "on-demand":',
        '                if mode == "on-demand":',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '            if request.mode == "on-demand":',
        '            if mode == "on-demand":',
    )
    patch(
        "src/linkedin_apply_assistant/workflows.py",
        '        "command": "assist", "mode": request.mode,',
        '        "command": "assist", "mode": mode,',
    )

    ats = ROOT / "src/linkedin_apply_assistant/ats_handlers.py"
    text = ats.read_text(encoding="utf-8")
    text = text.replace(
        '        configured = documents.get(kind) or documents.get(f"{kind}_path")\n        if configured and set_file_first(page, selectors, configured):\n            filled.append(f"document:{kind}")\n        elif kind in required:\n            missing.append(f"{kind} document path is required but not configured or readable.")',
        '        configured = documents.get(kind) or documents.get(f"{kind}_path")\n        if configured:\n            if set_file_first(page, selectors, configured):\n                filled.append(f"document:{kind}")\n            elif kind in required:\n                missing.append(f"{kind} document path is missing or unreadable.")\n        elif kind in required:\n            missing.append(f"{kind} document path is required but not configured.")',
    )
    text = text.replace(
        '            pending = bank.log_pending(\n                label, context=context, field_type=field_type, is_required=required_question\n            ) if bank else {"question": label, "field_type": field_type, "required": required_question}',
        '            pending = bank.log_pending(\n                label, context=context, field_type=field_type, is_required=required_question\n            ) if bank else {\n                "question": label, "field_type": field_type, "required": required_question,\n                "company": normalize_space(context.get("company")),\n                "role": normalize_space(context.get("role") or context.get("title")),\n                "ats": normalize_space(context.get("ats")),\n                "domain": normalize_space(context.get("domain")),\n            }',
    )
    ats.write_text(text, encoding="utf-8")


def patch_readme_and_distribution() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "npm install -g linkedin-apply-assistant" not in text:
        anchor = "Python source or pipx is the supported installation path. The npm artifact is a transparent launcher only and does not install Python dependencies."
        replacement = (
            "Python source or pipx is the supported installation path. The npm artifact is a transparent launcher only and does not install Python dependencies.\n\n"
            "NPM compatibility launcher:\n\n```bash\nnpm install -g linkedin-apply-assistant\n```"
        )
        text = text.replace(anchor, replacement)
    pinned = "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1"
    if pinned not in text:
        marker = "Windows PowerShell:\n\n```powershell\n"
        safe = (
            "Windows PowerShell (pinned, inspectable installer):\n\n```powershell\n"
            "$script = Join-Path $env:TEMP 'job-apply-assistant-install.ps1'\n"
            f"iwr {pinned} -OutFile $script\n"
            "# Inspect the script and tagged archive, then provide the verified archive SHA-256:\n"
            "& $script -Ref v0.1.5 -ExpectedSha256 <verified-sha256>\n"
        )
        text = text.replace(marker, safe, 1)
    readme.write_text(text, encoding="utf-8")

    package = ROOT / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    files = list(data.get("files") or [])
    if "requirements.lock" not in files:
        files.append("requirements.lock")
    data["files"] = files
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def patch_tests() -> None:
    for test in ROOT.glob("tests/test_*.py"):
        text = test.read_text(encoding="utf-8")
        text = text.replace(
            '        "docs/repository-hardening.md",\n',
            '        "docs/repository-hardening.md",\n        "requirements.lock",\n',
        )
        # Scrapling was unused runtime surface; remove direct expectations tied to it.
        lines = []
        for line in text.splitlines(keepends=True):
            if "scrapling" in line.lower() and "assert" in line:
                continue
            lines.append(line)
        test.write_text("".join(lines), encoding="utf-8")

    docs_test = ROOT / "tests/test_docs_smoke.py"
    if docs_test.exists():
        text = docs_test.read_text(encoding="utf-8")
        pinned = "https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/v0.1.5/install.ps1"
        text = text.replace(f'"irm {pinned} | iex"', '"expectedsha256"')
        text = text.replace(
            f'lower_text.count(\n            "irm {pinned} | iex"\n        )\n        == 1',
            '"expectedsha256" in lower_text and "| iex" not in lower_text',
        )
        text = text.replace(
            f'assert (\n        "raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1"\n        in text\n    )',
            'assert "ExpectedSha256" in text',
        )
        docs_test.write_text(text, encoding="utf-8")


def update_manifest_and_cleanup() -> None:
    for relative in (
        ".github/workflows/apply-audit-remediation.yml",
        ".github/workflows/apply-audit-remediation-v2.yml",
        ".github/workflows/apply-audit-remediation-v3.yml",
        ".github/workflows/apply-audit-remediation-v4.yml",
        ".github/workflows/apply-audit-remediation-v5.yml",
        "scripts/_audit_remediation_probe.txt",
        "scripts/_remediate_core_20260820.py",
        "scripts/_remediate_browser_20260820.py",
        "scripts/_remediate_supply_20260820.py",
        "scripts/_remediate_compat_20260820.py",
        "scripts/_run_audit_remediation_20260820.py",
        "scripts/_remediate_hotfix_20260820.py",
        "scripts/_remediate_finalize_20260820.py",
        "scripts/_remediate_final_compat_20260820.py",
        "scripts/_remediate_release_compat_20260820.py",
    ):
        (ROOT / relative).unlink(missing_ok=True)
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
    patch_source_contracts()
    patch_readme_and_distribution()
    patch_tests()
    update_manifest_and_cleanup()


if __name__ == "__main__":
    main()
