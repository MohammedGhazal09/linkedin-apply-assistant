from __future__ import annotations

import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from urllib.parse import unquote

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
README = PACKAGE_ROOT / "README.md"
SAFETY = PACKAGE_ROOT / "SAFETY.md"
INSTALL_DOC = PACKAGE_ROOT / "docs" / "install-and-configuration.md"
COMMANDS_DOC = PACKAGE_ROOT / "docs" / "commands.md"
REQUIRED_DOCS = (
    "README.md",
    "SAFETY.md",
    "LEGAL.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "MIGRATION.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "RELEASE_CHECKLIST.md",
    "docs/install-and-configuration.md",
    "docs/commands.md",
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

    for command in ("search", "assist", "apply", "dry-run", "report"):
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
        "python -m linkedin_apply_assistant.cli --help",
        "npm pack --dry-run --json",
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
    ):
        assert phrase in lower_text


def test_command_reference_is_linked_from_public_entry_points() -> None:
    readme = _read(README)
    install_doc = _read(INSTALL_DOC)
    troubleshooting = _read(PACKAGE_ROOT / "docs" / "troubleshooting.md")

    assert "docs/commands.md" in readme
    assert "commands.md" in install_doc
    assert "commands.md" in troubleshooting


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
    assert "python -m linkedin_apply_assistant.cli --help" in text
    assert "source, python, npm launcher, and playwright install matrix" in lower_text
    assert "no-submit" in lower_text

    # README is a quick start; the exhaustive install matrix belongs in docs/.
    assert lower_text.count("pipx install") == 0
    assert lower_text.count("npm install -g") == 0


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
    with tarfile.open(tarball, "r:gz") as archive:
        archive.extractall(unpack_dir)

    packed_root = unpack_dir / "package"
    packed_doc_paths = tuple(
        packed_root / doc_path.relative_to(PACKAGE_ROOT) for doc_path in DOC_PATHS
    )
    for doc_path in packed_doc_paths:
        assert doc_path.is_file(), doc_path.relative_to(packed_root)

    _assert_doc_links_exist(packed_doc_paths, packed_root)
