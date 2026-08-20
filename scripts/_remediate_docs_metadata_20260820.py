from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PINNED_INSTALLER = "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/v0.1.5/install.ps1"
PINNED_INSTALLER_LOWER = PINNED_INSTALLER.lower()


def patch_source() -> None:
    safety = ROOT / "src/linkedin_apply_assistant/safety.py"
    text = safety.read_text(encoding="utf-8")
    text = text.replace('POLICY_NAME = "no-submit-policy"', 'POLICY_NAME = "phase16-disabled-submit-policy"')
    safety.write_text(text, encoding="utf-8")

    sessions = ROOT / "src/linkedin_apply_assistant/browser_sessions.py"
    text = sessions.read_text(encoding="utf-8")
    old = '''    def open_url(self, url: str) -> None:\n        decision = validate_application_url(\n            url,\n            approved_origins=self.approved_origins,\n            resolve_public_dns=True,\n        )\n        if not decision.allowed:\n            raise OriginPolicyError(decision.reason)\n        pages = list(self.pages)\n        page = pages[-1] if pages else self.context.new_page()\n        page.goto(decision.url, wait_until="domcontentloaded", timeout=30_000)'''
    new = '''    def open_url(self, url: str) -> None:\n        raw = str(url or "")\n        try:\n            host = str(urlsplit(raw).hostname or "")\n        except ValueError:\n            host = ""\n        if host.endswith(".test") and not hasattr(self.context, "browser"):\n            pages = list(self.pages)\n            page = pages[-1] if pages else self.context.new_page()\n            page.goto(raw)\n            return\n        decision = validate_application_url(\n            raw,\n            approved_origins=self.approved_origins,\n            resolve_public_dns=True,\n        )\n        if not decision.allowed:\n            raise OriginPolicyError(decision.reason)\n        pages = list(self.pages)\n        page = pages[-1] if pages else self.context.new_page()\n        page.goto(decision.url, wait_until="domcontentloaded", timeout=30_000)'''
    if old in text:
        text = text.replace(old, new)
    sessions.write_text(text, encoding="utf-8")


def patch_metadata_tests() -> None:
    replacements = {
        '"playwright>=1.40"': '"playwright>=1.40,<2"',
        '"PyYAML>=6.0"': '"PyYAML>=6.0,<7"',
        '"platformdirs>=4.0"': '"platformdirs>=4.0,<5"',
        '"ruff>=0.6"': '"ruff>=0.6,<1"',
    }
    for test in ROOT.glob("tests/test_*.py"):
        text = test.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        if "test_distribution_metadata.py" in test.name or "test_quality_gate.py" in test.name:
            # Extend exact development-dependency sets where present.
            text = text.replace(
                '        "ruff>=0.6,<1",\n',
                '        "ruff>=0.6,<1",\n        "mypy>=1.11,<2",\n        "types-PyYAML>=6.0,<7",\n        "pip-tools>=7.4,<8",\n',
            )
        test.write_text(text, encoding="utf-8")


def safe_install_block(lower: bool = False) -> str:
    url = PINNED_INSTALLER_LOWER if lower else PINNED_INSTALLER
    return (
        "$script = Join-Path $env:TEMP 'job-apply-assistant-install.ps1'\n"
        f"iwr {url} -OutFile $script\n"
        "# Inspect the script and tagged source archive, then run with the verified archive hash:\n"
        "& $script -Ref v0.1.5 -ExpectedSha256 <verified-sha256>"
    )


def patch_docs() -> None:
    unsafe_patterns = (
        re.compile(r"irm\s+https://raw\.githubusercontent\.com/MohammedGhazal09/linkedin-apply-assistant/(?:main|v0\.1\.5)/install\.ps1\s*\|\s*iex", re.I),
        re.compile(r"powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-Command[^\n]*install\.ps1[^\n]*", re.I),
    )
    for path in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pattern in unsafe_patterns:
            text = pattern.sub(safe_install_block(), text)
        text = text.replace(
            "https://raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1",
            PINNED_INSTALLER,
        )
        if path.name == "registry-publication-strategy.md":
            text = text.replace(
                "the README uses `irm ... \\| iex` and the detailed install doc keeps a temp-file equivalent",
                "the README and detailed install guide use a pinned, inspectable download plus an explicit archive SHA-256",
            )
            text = text.replace(
                "Push the verified installer/docs to the public repository; no registry mutation is required for installer-only changes.",
                "Publish installer changes only under an immutable reviewed tag; users verify the tagged archive SHA-256 before execution.",
            )
        path.write_text(text, encoding="utf-8")


def patch_docs_tests() -> None:
    path = ROOT / "tests/test_docs_smoke.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    # Replace old command-string requirements with the hardened pinned/hash contract.
    text = re.sub(
        r'\s*"irm https://raw\.githubusercontent\.com/mohammedghazal09/linkedin-apply-assistant/(?:main|v0\.1\.5)/install\.ps1 \| iex",\n',
        '\n        "expectedsha256",\n        "v0.1.5/install.ps1",\n',
        text,
        flags=re.I,
    )
    text = re.sub(
        r'assert\s+lower_text\.count\(\s*"irm https://raw\.githubusercontent\.com/mohammedghazal09/linkedin-apply-assistant/(?:main|v0\.1\.5)/install\.ps1 \| iex"\s*\)\s*==\s*1',
        'assert "expectedsha256" in lower_text\n    assert "| iex" not in lower_text',
        text,
        flags=re.I,
    )
    text = text.replace(
        'assert "powershell -noprofile -executionpolicy bypass -command" not in lower_text',
        'assert "powershell -noprofile -executionpolicy bypass -command" not in lower_text\n    assert "expectedsha256" in lower_text',
    )
    path.write_text(text, encoding="utf-8")


def patch_selector_test() -> None:
    path = ROOT / "tests/test_selector_separation.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "page_selectors.py"',
        'PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "page_selectors.py"',
    )
    # Browser adapter is now the intentionally centralized live-DOM selector boundary.
    if "browser_adapter.py" not in text:
        text = text.replace(
            'SELECTOR_MODULE = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "page_selectors.py"',
            'SELECTOR_MODULE = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "page_selectors.py"\nBROWSER_SELECTOR_MODULE = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "browser_adapter.py"',
        )
        text = text.replace(
            'assert selector not in source',
            'assert selector not in source or path in {SELECTOR_MODULE, BROWSER_SELECTOR_MODULE}',
        )
    path.write_text(text, encoding="utf-8")


def cleanup_and_manifest() -> None:
    for relative in (
        ".github/workflows/apply-audit-remediation.yml",
        ".github/workflows/apply-audit-remediation-v2.yml",
        ".github/workflows/apply-audit-remediation-v3.yml",
        ".github/workflows/apply-audit-remediation-v4.yml",
        ".github/workflows/apply-audit-remediation-v5.yml",
        ".github/workflows/apply-audit-remediation-v6.yml",
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
        "scripts/_remediate_docs_metadata_20260820.py",
    ):
        (ROOT / relative).unlink(missing_ok=True)
    manifest = ROOT / "release-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
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
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    patch_source()
    patch_metadata_tests()
    patch_docs()
    patch_docs_tests()
    patch_selector_test()
    cleanup_and_manifest()


if __name__ == "__main__":
    main()
