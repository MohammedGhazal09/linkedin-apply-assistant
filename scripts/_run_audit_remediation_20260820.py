from __future__ import annotations

import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "fix/audit-remediation-all-findings"
TEMP_FILES = (
    ".github/workflows/export-source.yml",
    ".github/workflows/apply-audit-remediation.yml",
    "scripts/_audit_remediation_probe.txt",
    "scripts/_remediate_core_20260820.py",
    "scripts/_remediate_browser_20260820.py",
    "scripts/_remediate_supply_20260820.py",
    "scripts/_remediate_compat_20260820.py",
    "scripts/_run_audit_remediation_20260820.py",
)


def run(*args: str) -> str:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def resolve_action(repository: str, tag: str) -> str:
    output = run("git", "ls-remote", f"https://github.com/{repository}.git", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    lines = [line.split() for line in output.splitlines() if line.strip()]
    peeled = next((sha for sha, ref in lines if ref.endswith("^{}")), None)
    direct = next((sha for sha, ref in lines if ref == f"refs/tags/{tag}"), None)
    sha = peeled or direct
    if not sha or len(sha) != 40:
        raise RuntimeError(f"Could not resolve immutable SHA for {repository}@{tag}")
    return sha


def apply_generators() -> None:
    for name in (
        "_remediate_core_20260820.py",
        "_remediate_browser_20260820.py",
        "_remediate_supply_20260820.py",
        "_remediate_compat_20260820.py",
    ):
        namespace = runpy.run_path(str(ROOT / "scripts" / name))
        namespace["apply"]()


def write_ci() -> None:
    checkout = resolve_action("actions/checkout", "v4")
    setup_python = resolve_action("actions/setup-python", "v6")
    setup_node = resolve_action("actions/setup-node", "v6")
    codeql = resolve_action("github/codeql-action", "v4")
    dependency_review = resolve_action("actions/dependency-review-action", "v5")
    gitleaks = resolve_action("gitleaks/gitleaks-action", "v3")

    quality = f'''name: Quality

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  unit:
    name: unit-${{{{ matrix.os }}}}-py${{{{ matrix.python }}}}
    runs-on: ${{{{ matrix.os }}}}
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@{checkout}
      - uses: actions/setup-python@{setup_python}
        with:
          python-version: ${{{{ matrix.python }}}}
          cache: pip
      - name: Install locked dependencies and package
        shell: bash
        run: |
          python -m pip install --upgrade pip
          python -m pip install --require-hashes -r requirements.lock
          python -m pip install --no-deps -e .
      - name: Compile, test, lint, format, and type-check
        shell: bash
        run: |
          python -m compileall -q src tests
          python -m pytest tests -q -m "not live"
          python -m ruff check --no-cache src tests
          python -m ruff format --check --no-cache src tests
          python -m mypy src/linkedin_apply_assistant
      - name: Audit locked dependency closure
        shell: bash
        run: python -m pip_audit --requirement requirements.lock --no-deps --progress-spinner off

  browser-fixtures:
    name: chromium-fixtures
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@{checkout}
      - uses: actions/setup-python@{setup_python}
        with:
          python-version: "3.12"
          cache: pip
      - name: Install locked dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install --require-hashes -r requirements.lock
          python -m pip install --no-deps -e .
          python -m playwright install --with-deps chromium
      - name: Run deterministic browser fixtures
        run: python -m pytest tests/test_browser_e2e.py -q -m live

  release-smoke:
    name: release-smoke
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: [unit, browser-fixtures]
    steps:
      - uses: actions/checkout@{checkout}
      - uses: actions/setup-python@{setup_python}
        with:
          python-version: "3.12"
          cache: pip
      - uses: actions/setup-node@{setup_node}
        with:
          node-version: "24"
      - name: Install locked dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install --require-hashes -r requirements.lock
          python -m pip install --no-deps -e .
      - name: Verify release candidate
        run: |
          python scripts/release.py clean
          python scripts/release.py manifest --check
          python scripts/release.py verify
          npm pack --dry-run --json

  windows-installer:
    name: windows-installer-parser
    runs-on: windows-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@{checkout}
      - name: Parse pinned installer
        shell: powershell
        run: |
          $errors=$null
          [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw .\install.ps1), [ref]$errors) | Out-Null
          if($errors){{$errors; exit 1}}
          .\install.ps1 -CheckOnly -Ref v0.1.5
'''
    security = f'''name: Security

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "17 4 * * 2"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  codeql:
    name: codeql-${{{{ matrix.language }}}}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript]
    steps:
      - uses: actions/checkout@{checkout}
      - uses: github/codeql-action/init@{codeql}
        with:
          languages: ${{{{ matrix.language }}}}
          queries: security-extended
      - uses: github/codeql-action/analyze@{codeql}
        with:
          category: /language:${{{{ matrix.language }}}}

  dependency-review:
    name: dependency-review
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@{checkout}
      - uses: actions/dependency-review-action@{dependency_review}
        with:
          fail-on-severity: high

  secret-scan:
    name: secret-scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@{checkout}
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@{gitleaks}
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
          GITLEAKS_ENABLE_COMMENTS: "false"

  dependency-audit:
    name: dependency-audit
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@{checkout}
      - uses: actions/setup-python@{setup_python}
        with:
          python-version: "3.12"
          cache: pip
      - run: |
          python -m pip install pip-audit
          python -m pip_audit --requirement requirements.lock --no-deps --progress-spinner off
'''
    (ROOT / ".github/workflows/quality.yml").write_text(quality, encoding="utf-8")
    (ROOT / ".github/workflows/security.yml").write_text(security, encoding="utf-8")
    (ROOT / ".github/CODEOWNERS").write_text("* @MohammedGhazal09\n", encoding="utf-8")

    test = ROOT / "tests/test_workflow_safety.py"
    if test.exists():
        text = test.read_text(encoding="utf-8")
        text = text.replace("actions/checkout@v7.0.0", f"actions/checkout@{checkout}")
        text = text.replace("actions/setup-python@v6.3.0", f"actions/setup-python@{setup_python}")
        text = text.replace("actions/setup-node@v6.4.0", f"actions/setup-node@{setup_node}")
        text = text.replace("github/codeql-action/init@v4.36.3", f"github/codeql-action/init@{codeql}")
        text = text.replace("github/codeql-action/analyze@v4.36.3", f"github/codeql-action/analyze@{codeql}")
        text = text.replace("actions/dependency-review-action@v5.0.0", f"actions/dependency-review-action@{dependency_review}")
        text = text.replace("gitleaks/gitleaks-action@v3.0.0", f"gitleaks/gitleaks-action@{gitleaks}")
        test.write_text(text, encoding="utf-8")


def generate_lock() -> None:
    run(
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "pyproject.toml",
        "--extra",
        "dev",
        "--generate-hashes",
        "--strip-extras",
        "--resolver",
        "backtracking",
        "--output-file",
        "requirements.lock",
    )


def patch_changelog_and_docs() -> None:
    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    entry = '''## [Unreleased]\n\n### Security\n\n- Replaced fake-only browser hooks with a real, origin-verified Playwright adapter and deterministic Chromium fixtures.\n- Added hostname-only ATS trust, explicit generic-origin approval, multi-step required-field blocking, and a hard no-submit state machine.\n- Added versioned bounded schemas, workspace path confinement, private atomic storage, report integrity manifests, and conservative sensitive-question matching.\n- Disabled mutable PowerShell self-update execution; the installer now requires an immutable ref and verified archive SHA-256.\n- Pinned GitHub Actions to immutable commits and added cross-platform, browser, type, dependency, release, and installer verification.\n\n### Changed\n\n- Product display branding is now Job Apply Assistant with an explicit non-affiliation notice; historical package identifiers remain for compatibility.\n'''
    text = text.replace("## [Unreleased]\n", entry, 1)
    changelog.write_text(text, encoding="utf-8")

    hardening = ROOT / "docs/repository-hardening.md"
    hardening.write_text(
        """# Repository Hardening\n\nThe committed workflows expose immutable `Quality` and `Security` checks. Repository administrators should configure the `main` ruleset to require pull requests, one approving review, conversation resolution, signed commits where operationally feasible, and these checks: all `unit-*` jobs, `chromium-fixtures`, `release-smoke`, `windows-installer-parser`, `codeql-python`, `codeql-javascript`, `dependency-review`, `secret-scan`, and `dependency-audit`.\n\nPrivate vulnerability reports use GitHub Security Advisories. Publishing credentials are intentionally absent; future registry publication requires protected environments and OIDC.\n""",
        encoding="utf-8",
    )


def remove_temporary_files() -> None:
    for relative in TEMP_FILES:
        (ROOT / relative).unlink(missing_ok=True)


def category(path: str) -> str:
    if path.startswith("src/"):
        return "source"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith(".github/workflows/") or path == ".github/dependabot.yml":
        return "ci"
    if path.startswith(".github/"):
        return "community-template"
    if path.startswith("docs/") or path.endswith(".md"):
        return "docs"
    if path.startswith("configs/"):
        return "example-config"
    if path.startswith("examples/"):
        return "example"
    if path.startswith("scripts/"):
        return "tooling"
    if path == "install.ps1":
        return "installer"
    if path == "package.json":
        return "npm-metadata"
    if path in {"pyproject.toml", "requirements.lock"}:
        return "package-metadata"
    if path in {"LICENSE", "THIRD_PARTY_NOTICES.md"}:
        return "license"
    if path == "release-manifest.json":
        return "release"
    return "config"


def update_manifest() -> None:
    excluded_parts = {
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
        "venv", "build", "dist", "node_modules", "output", "browser-profile", "data",
    }
    files: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in excluded_parts or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.name.endswith((".tgz", ".whl")):
            continue
        files.append(relative.as_posix())
    if "release-manifest.json" not in files:
        files.append("release-manifest.json")
    manifest_path = ROOT / "release-manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest = {
        "schema_version": 1,
        "package": "linkedin-apply-assistant",
        "source_root": ".",
        "generated_note": "Comprehensive audit-remediation manifest generated from the verified tracked tree.",
        "no_publish_scope": "Verification only; no registry publication, release, or tag mutation.",
        "blocked_patterns": old.get("blocked_patterns", [".env", "data/", "output/", "browser-profile/", "dist/", "build/"]),
        "files": [{"path": path, "category": category(path)} for path in sorted(set(files))],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    apply_generators()
    generate_lock()
    write_ci()
    patch_changelog_and_docs()
    remove_temporary_files()
    update_manifest()


if __name__ == "__main__":
    main()
