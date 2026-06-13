from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
README = PACKAGE_ROOT / "README.md"
SAFETY = PACKAGE_ROOT / "SAFETY.md"
INSTALL_DOC = PACKAGE_ROOT / "docs" / "install-and-configuration.md"
COMMANDS_DOC = PACKAGE_ROOT / "docs" / "commands.md"
CI_POLICY_DOC = PACKAGE_ROOT / "docs" / "ci-and-release-policy.md"
REGISTRY_STRATEGY_DOC = PACKAGE_ROOT / "docs" / "registry-publication-strategy.md"
REQUIRED_DOCS = (
    "README.md",
    "SAFETY.md",
    "LEGAL.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "MIGRATION.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "CODE_OF_CONDUCT.md",
    "install.ps1",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "CHANGELOG.md",
    "RELEASE_CHECKLIST.md",
    "docs/install-and-configuration.md",
    "docs/commands.md",
    "docs/ci-and-release-policy.md",
    "docs/registry-publication-strategy.md",
    "docs/browser-session.md",
    "docs/search.md",
    "docs/assist.md",
    "docs/apply.md",
    "docs/reports.md",
    "docs/troubleshooting.md",
    "configs/config.example.yml",
    "configs/qa_bank.example.yml",
    "examples/dry_run_input.example.json",
    "examples/reports/search-report.example.json",
    "examples/reports/apply-audit.example.json",
)
DOC_PATHS = tuple(PACKAGE_ROOT / path for path in REQUIRED_DOCS if path.endswith(".md"))
INSTALL_SURFACES = (README, INSTALL_DOC)
PUBLIC_REPO = "https://github.com/MohammedGhazal09/linkedin-apply-assistant"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _safe_tar_target(root: Path, member: tarfile.TarInfo) -> Path:
    member_path = PurePosixPath(member.name)
    if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
        raise ValueError(f"unsafe tar member path: {member.name}")

    target = (root / Path(*member_path.parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"tar member resolves outside target directory: {member.name}")
    return target


def _extract_tarball_safely(tarball: Path, target_dir: Path) -> None:
    root = target_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            target = _safe_tar_target(root, member)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(f"unsupported tar member type: {member.name}")

            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"tar member has no file content: {member.name}")

            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _assert_doc_links_exist(doc_paths: tuple[Path, ...], root: Path) -> None:
    resolved_root = root.resolve()

    for doc_path in doc_paths:
        docs = _read(doc_path)
        linked_paths = re.findall(r"\]\(([^)#][^)]+)\)", docs)

        for linked_path in linked_paths:
            if "://" in linked_path or linked_path.startswith("mailto:"):
                continue
            target = unquote(linked_path.split("#", 1)[0])
            if not target:
                continue
            resolved_target = (doc_path.parent / target).resolve()
            assert resolved_target.is_relative_to(resolved_root), (
                f"{doc_path.name}: {linked_path} points outside package root"
            )
            assert resolved_target.exists(), f"{doc_path.name}: {linked_path}"


def test_required_public_docs_exist() -> None:
    for relative_path in REQUIRED_DOCS:
        assert (PACKAGE_ROOT / relative_path).is_file(), relative_path


def test_readme_names_public_cli_commands() -> None:
    text = _read(README).lower()

    for command in ("search", "assist", "apply", "dry-run", "report", "update"):
        assert re.search(rf"`{re.escape(command)}`", text)


def test_docs_cover_shared_cli_flags() -> None:
    docs = "\n".join(_read(path) for path in DOC_PATHS).lower()

    for flag in (
        "--workspace",
        "--config",
        "--qa-bank",
        "--browser-profile",
        "--output-dir",
        "--verbose",
    ):
        assert flag in docs


def test_apply_docs_preserve_prepare_only_boundary() -> None:
    docs = f"{_read(README)}\n{_read(PACKAGE_ROOT / 'docs' / 'apply.md')}".lower()

    for phrase in (
        "prepare-only",
        "no-submit",
        "browser submission remains disabled",
        "explicit per-submission confirmation",
    ):
        assert phrase in docs


def test_package_root_command_blocks_do_not_use_monorepo_path() -> None:
    package_root_docs = (
        PACKAGE_ROOT / "CONTRIBUTING.md",
        PACKAGE_ROOT / "RELEASE_CHECKLIST.md",
        PACKAGE_ROOT / "docs" / "commands.md",
        PACKAGE_ROOT / "docs" / "install-and-configuration.md",
        PACKAGE_ROOT / "docs" / "troubleshooting.md",
    )

    for path in package_root_docs:
        text = _read(path)
        assert "Push-Location standalone\\linkedin-apply-assistant" not in text, path.name
        assert "Pop-Location" not in text, path.name


def test_install_docs_cover_source_python_and_playwright_paths() -> None:
    text = _read(INSTALL_DOC)
    lower_text = text.lower()

    for phrase in (
        "public source download",
        f"git clone {PUBLIC_REPO}.git",
        "zip/tarball",
        "python -m pip install .",
        'python -m pip install -e ".[dev]"',
        "pipx install .",
        "pipx install linkedin-apply-assistant",
        "npm install -g linkedin-apply-assistant",
        "npm install -g linkedin-apply-assistant@latest",
        "powershell installer",
        "install.ps1",
        "irm https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1 | iex",
        "inspectable temp-file equivalent",
        "raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1",
        "py -3 -m pip install $pkg",
        "python -m linkedin_apply_assistant.cli --help",
        "npm pack --dry-run --json",
        "linkedin-apply-assistant update",
        "linkedin-apply-assistant update --check",
        "& $script -update",
        "& $script -checkonly",
    ):
        assert phrase.lower() in lower_text

    assert text.count("python -m playwright install chromium") == 1
    assert "browser-free commands" in lower_text
    assert "dry-run" in lower_text
    assert "`report` reads a local report json file" in lower_text


def test_command_reference_covers_first_run_workflows_and_paths() -> None:
    text = _read(COMMANDS_DOC)
    lower_text = text.lower()

    for phrase in (
        "first-run checklist",
        "linkedin-apply-assistant config check",
        "search",
        "assist",
        "apply",
        "dry-run",
        "report",
        "update",
        "config file",
        "q&a bank",
        "browser profile",
        "output directory",
        "reports directory",
        "data directory",
        "cache directory",
        "configs/config.example.yml",
        "configs/qa_bank.example.yml",
        "answer truthfully",
        "python -m playwright install chromium",
        "no-submit",
        "fill-only",
        "browser submission remains disabled",
        "try: linkedin-apply-assistant config check",
        "linkedin-apply-assistant update --check",
        "npm install -g linkedin-apply-assistant@latest",
    ):
        assert phrase in lower_text


def test_command_reference_is_linked_from_public_entry_points() -> None:
    readme = _read(README)
    install_doc = _read(INSTALL_DOC)
    troubleshooting = _read(PACKAGE_ROOT / "docs" / "troubleshooting.md")

    assert "docs/commands.md" in readme
    assert "commands.md" in install_doc
    assert "commands.md" in troubleshooting


def test_readme_and_contributing_link_community_health_files() -> None:
    readme = _read(README)
    contributing = _read(PACKAGE_ROOT / "CONTRIBUTING.md")
    combined = f"{readme}\n{contributing}"

    for relative_path in (
        "SUPPORT.md",
        "GOVERNANCE.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/ISSUE_TEMPLATE/",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ):
        assert relative_path in combined


def test_readme_links_ci_policy_and_workflow_badges() -> None:
    readme = _read(README)

    for phrase in (
        "actions/workflows/quality.yml/badge.svg?branch=main",
        "actions/workflows/security.yml/badge.svg?branch=main",
        "actions/workflows/quality.yml?query=branch%3Amain",
        "actions/workflows/security.yml?query=branch%3Amain",
        "docs/ci-and-release-policy.md",
    ):
        assert phrase in readme


def test_ci_policy_documents_active_and_deferred_controls() -> None:
    text = _read(CI_POLICY_DOC).lower()

    for phrase in (
        "quality",
        "security",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
        "python `3.11` and `3.12`",
        "node.js `24`",
        'python -m pip install -e ".[dev]"',
        "npm pack --dry-run --json",
        "codeql",
        "dependency-review",
        "fail-on-severity: high",
        "gitleaks",
        "contents: read",
        "security-events: write",
        "sbom generation",
        "artifact attestations",
        "id-token: write",
        "attestations: write",
        "packages: write",
        "release please",
        "semantic-release",
        "conventional commits",
        "no-surprise publish boundary",
        "registry-publication-strategy.md",
    ):
        assert phrase in text

    for phrase in (
        "npm publish",
        "twine upload",
        "create or push tags",
        "mutate branch rulesets",
    ):
        assert phrase in text


def test_registry_publication_strategy_is_part_of_public_docs() -> None:
    text = _read(REGISTRY_STRATEGY_DOC).lower()
    readme = _read(README)
    install_doc = _read(INSTALL_DOC)

    assert "registry publication strategy" in text
    assert "docs/registry-publication-strategy.md" in readme
    assert "registry-publication-strategy.md" in install_doc
    assert "github releases" in text
    assert "pypi" in text
    assert "testpypi" in text
    assert "npm" in text


def test_command_reference_keeps_browser_free_commands_browser_free() -> None:
    text = _read(COMMANDS_DOC).lower()

    dry_run_section = text.split("## dry-run", 1)[1].split("## report", 1)[0]
    report_section = text.split("## report", 1)[1]
    for section in (dry_run_section, report_section):
        assert "browser-free" in section
        assert "does not require playwright" in section
        assert "does not require a browser profile" in section


def test_readme_points_to_canonical_install_matrix_without_duplicating_it() -> None:
    text = _read(README)
    lower_text = text.lower()

    assert "docs/install-and-configuration.md" in text
    assert "python 3.11" in lower_text
    assert "linkedin-apply-assistant --help" in text
    assert (
        "raw.githubusercontent.com/MohammedGhazal09/linkedin-apply-assistant/main/install.ps1"
        in text
    )
    assert "source, Python, Playwright, and troubleshooting details" in text
    assert "no-submit" in lower_text

    # README is a quick start; detailed install paths belong in docs/.
    assert lower_text.count("pipx install") == 0
    assert lower_text.count("npm install -g") == 1
    assert (
        lower_text.count(
            "irm https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1 | iex"
        )
        == 1
    )
    assert "powershell -noprofile -executionpolicy bypass -command" not in lower_text
    assert "py -3 -m pip install $pkg" not in lower_text
    assert 'python -m pip install -e ".[dev]"' not in lower_text
    assert "python -m linkedin_apply_assistant.cli --help" not in lower_text


def test_install_docs_avoid_live_availability_claims_before_ship_approval() -> None:
    text = "\n".join(_read(path) for path in INSTALL_SURFACES)
    lower_text = text.lower()

    forbidden_phrases = (
        "published on npm",
        "published on pypi",
        "npm publish",
        "pypi publish",
        "testpypi publish",
    )
    for phrase in forbidden_phrases:
        assert phrase not in lower_text

    assert "<future-public-repository-url>" not in text
    assert "future public repository" not in lower_text
    assert PUBLIC_REPO in text
    assert "npm install -g linkedin-apply-assistant" in lower_text
    assert "pypi remains a future package channel" in lower_text


def test_docs_preserve_safety_and_platform_boundaries() -> None:
    docs = "\n".join(_read(path) for path in DOC_PATHS).lower()

    for phrase in (
        "no-submit",
        "per-application interactive confirmation",
        "platform",
        "browser profile",
        "not legal advice",
        "not a compliance certification",
    ):
        assert phrase in docs


def test_docs_do_not_reference_missing_package_files() -> None:
    _assert_doc_links_exist(DOC_PATHS, PACKAGE_ROOT)


def test_safe_tarball_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    tarball = tmp_path / "malicious.tgz"
    with tarfile.open(tarball, "w:gz") as archive:
        payload = b"outside"
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(ValueError, match="unsafe tar member path"):
        _extract_tarball_safely(tarball, tmp_path / "unpacked")


def test_packed_npm_docs_do_not_reference_missing_package_files(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm is not available; source docs link checks still ran")

    result = subprocess.run(
        [npm, "pack", str(PACKAGE_ROOT), "--json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload

    tarball = tmp_path / payload[0]["filename"]
    unpack_dir = tmp_path / "unpacked"
    _extract_tarball_safely(tarball, unpack_dir)

    packed_root = unpack_dir / "package"
    packed_doc_paths = tuple(
        packed_root / doc_path.relative_to(PACKAGE_ROOT) for doc_path in DOC_PATHS
    )
    for doc_path in packed_doc_paths:
        assert doc_path.is_file(), doc_path.relative_to(packed_root)

    _assert_doc_links_exist(packed_doc_paths, packed_root)
