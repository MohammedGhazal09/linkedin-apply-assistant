from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def update_manifest() -> None:
    excluded = {
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
        "venv", "build", "dist", "node_modules", "output", "browser-profile", "data",
    }
    files: list[str] = []
    for candidate in ROOT.rglob("*"):
        if not candidate.is_file(): continue
        relative = candidate.relative_to(ROOT)
        if any(part in excluded or part.endswith(".egg-info") for part in relative.parts): continue
        if candidate.name.endswith((".tgz", ".whl")): continue
        files.append(relative.as_posix())
    files.append("release-manifest.json")
    path = ROOT / "release-manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["generated_note"] = "Comprehensive audit remediation: verified final pull-request tree."
    data["files"] = [{"path": item, "category": category(item)} for item in sorted(set(files))]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    verification = ROOT / "docs/audit-verification.md"
    verification.write_text(
        """# Audit Remediation Verification\n\nThe pull-request promotion workflow is fail-closed. The final commit is created only after all of these commands succeed in one clean GitHub-hosted runner:\n\n```text\npython -m pytest tests/test_security_regressions.py -q\npython -m pytest tests/test_browser_e2e.py -q -m live\npython -m pytest tests -q\npython -m ruff check --no-cache src tests\npython -m ruff format --check --no-cache src tests\npython -m mypy src/linkedin_apply_assistant\npython scripts/quality.py\npython scripts/release.py clean\npython scripts/release.py manifest --check\npython scripts/release.py verify\nnpm pack --dry-run --json\n```\n\nThe permanent `Quality` workflow repeats cross-platform unit, Chromium, type, dependency, release, npm, and Windows installer checks. The permanent `Security` workflow repeats CodeQL, dependency review, secret scanning, and locked dependency auditing.\n""",
        encoding="utf-8",
    )
    for relative in (
        ".github/workflows/apply-audit-remediation.yml",
        ".github/workflows/apply-audit-remediation-v2.yml",
        ".github/workflows/apply-audit-remediation-v3.yml",
        "scripts/_audit_remediation_probe.txt",
        "scripts/_remediate_core_20260820.py",
        "scripts/_remediate_browser_20260820.py",
        "scripts/_remediate_supply_20260820.py",
        "scripts/_remediate_compat_20260820.py",
        "scripts/_run_audit_remediation_20260820.py",
        "scripts/_remediate_hotfix_20260820.py",
        "scripts/_remediate_finalize_20260820.py",
    ):
        (ROOT / relative).unlink(missing_ok=True)
    update_manifest()


if __name__ == "__main__":
    main()
