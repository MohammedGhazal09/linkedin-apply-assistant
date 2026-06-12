from __future__ import annotations

from pathlib import Path
import re


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _checklist_text() -> str:
    return (PACKAGE_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8").lower()


def _checklist_command_blocks() -> str:
    checklist = (PACKAGE_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8").lower()
    return "\n".join(re.findall(r"```(?:powershell|text)?\n(.*?)```", checklist, flags=re.DOTALL))


PUBLIC_REPO = "https://github.com/mohammedghazal09/linkedin-apply-assistant"


def test_release_required_files_exist() -> None:
    for relative_path in (
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
    ):
        assert (PACKAGE_ROOT / relative_path).is_file(), relative_path


def test_release_checklist_tracks_hard_blockers() -> None:
    checklist = _checklist_text()

    for phrase in (
        "missing license",
        "missing notices",
        "private-data leaks",
        "stale commands",
        "unsafe submit wording",
        "python scripts\\quality.py",
        "phase 17 verification evidence",
        ".pytest_cache",
        ".ruff_cache",
        "build/",
        "dist/",
        "final packaging cleanup",
        "__pycache__",
        "*.egg-info",
        "-recurse",
        "distribution metadata drift",
        "python build smoke",
        "npm pack smoke",
        "npm launcher guardrails",
        "terminal help drift",
        "config diagnostics drift",
        "command reference drift",
        "browser setup guidance drift",
        "explicit no-publish approval",
    ):
        assert phrase in checklist


def test_top_level_generated_release_artifacts_are_absent_after_quality_gates() -> None:
    blocked_names = {".pytest_cache", ".ruff_cache", "build", "dist"}
    failures: list[str] = []

    for path in PACKAGE_ROOT.iterdir():
        if path.name in blocked_names:
            failures.append(str(path.relative_to(PACKAGE_ROOT)))

    assert not failures, "\n".join(failures)


def test_release_checklist_distinguishes_final_packaging_cleanup() -> None:
    checklist = _checklist_text()

    assert "automated post-quality artifact gate" in checklist
    assert "final publish gate" in checklist
    assert "normal verification" in checklist


def test_release_checklist_documents_pub07_public_metadata_workflow() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 23 pub-07 public metadata readiness",
        PUBLIC_REPO,
        "repository.url",
        "homepage",
        "bugs.url",
        "project urls",
        "real gitleaks evidence",
        "python scripts\\release.py clean",
        "python scripts\\release.py verify",
        "npm pack --dry-run --json",
        "no-publish proof",
        "v0.1.0",
        "phase 24",
        "changelog.md",
        "23-verification.md",
        "manual approval point",
        "git push",
        "git tag",
        "github release",
        "npm publish",
        "pypi publish",
        "testpypi publish",
        "delete the generated candidate",
        "do not reuse the failed candidate",
    ):
        assert phrase in checklist


def test_release_checklist_uses_specific_file_staging_only() -> None:
    checklist = _checklist_text()

    assert "specific-file staging only" in checklist
    assert "git add -- release_checklist.md changelog.md scripts\\release.py" in checklist
    assert "git add -a" not in checklist
    assert "git add ." not in checklist


def test_phase19_does_not_add_publishing_doc() -> None:
    assert not (PACKAGE_ROOT / "docs" / "publishing.md").exists()


def test_release_checklist_documents_phase20_distribution_gates() -> None:
    checklist = _checklist_text()

    for phrase in (
        "python -m pytest tests\\test_docs_smoke.py tests\\test_npm_launcher.py",
        "tests\\test_distribution_metadata.py",
        "tests\\test_distribution_smoke.py",
        "python -m build --outdir",
        "npm pack --dry-run --json",
        "python scripts\\release.py manifest --check",
        "python scripts\\release.py verify",
        "package.json",
        "repository",
        "homepage",
        "bugs",
        "source, python, and npm launcher install docs are current and tested",
        "without sending anything to a registry",
    ):
        assert phrase in checklist


def test_release_checklist_documents_phase21_terminal_ux_gates() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 21 terminal ux",
        "terminal help drift",
        "config diagnostics drift",
        "command reference drift",
        "browser setup guidance drift",
        "python -m pytest tests\\test_cli_help.py tests\\test_config_diagnostics.py",
        "docs\\commands.md",
        "tests\\test_cli_help.py",
        "tests\\test_config_diagnostics.py",
        "linkedin-apply-assistant config check",
        "python -m playwright install chromium",
        "no-submit",
        "browser submission remains disabled",
        "python scripts\\release.py verify",
    ):
        assert phrase in checklist


def test_release_checklist_documents_phase24_pub08_github_source_release() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 24 pub-08 v0.1.0 github source release",
        "mohammedghazal09/linkedin-apply-assistant",
        "tag: `v0.1.0`",
        "draft-first github release",
        "release-prep `main` commit",
        "push origin main",
        "origin/main",
        "--verify-tag",
        "refs/tags/v0.1.0",
        "then pushing only `refs/tags/v0.1.0`",
        "empty release assets",
        "gitleaks: passed",
        "no-registry proof",
        "rollback commands",
        "no npm publish",
        "no pypi publish",
        "no testpypi publish",
        "no registry token setup",
    ):
        assert phrase in checklist


def test_release_checklist_does_not_script_broad_tag_or_registry_publish() -> None:
    commands = _checklist_command_blocks()

    for forbidden in (
        "git push --tags",
        "git push origin --tags",
        "git push --mirror",
        "gh release verify",
        "npm publish",
        "twine upload",
    ):
        assert forbidden not in commands
