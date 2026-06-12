from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _checklist_text() -> str:
    return (PACKAGE_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8").lower()


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


def test_release_checklist_documents_phase19_no_publish_workflow() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 19 no-publish workflow",
        "release readiness only",
        "future clean standalone repository",
        "standalone/linkedin-apply-assistant",
        "main",
        "v0.1.0",
        "phases 20 and 21 pass",
        "explicit ship approval",
        "changelog.md",
        "19-verification.md",
        "manual approval point",
        "gh repo create",
        "git remote add",
        "git push",
        "git tag",
        "github release",
        "npm publish",
        "pypi publish",
        "delete the generated candidate",
        "do not reuse the failed candidate",
        "python scripts\\release.py clean",
        "python scripts\\release.py verify",
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
