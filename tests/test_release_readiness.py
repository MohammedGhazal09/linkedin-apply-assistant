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
        "SUPPORT.md",
        "GOVERNANCE.md",
        "CODE_OF_CONDUCT.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/docs.yml",
        ".github/ISSUE_TEMPLATE/safety_compliance.yml",
        ".github/ISSUE_TEMPLATE/config_help.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
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
        "explicit external-action approval",
        "registry state proof",
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
        "source, python, npm launcher, and powershell installer docs are current and tested",
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


def test_release_checklist_documents_phase26_community_health_gates() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 26 community health files and contribution templates",
        "support.md",
        "governance.md",
        "code_of_conduct.md",
        ".github/issue_template/bug_report.yml",
        ".github/issue_template/feature_request.yml",
        ".github/issue_template/docs.yml",
        ".github/issue_template/safety_compliance.yml",
        ".github/issue_template/config_help.yml",
        ".github/issue_template/config.yml",
        ".github/pull_request_template.md",
        "python -m pytest tests\\test_community_health.py",
        "python scripts\\release.py manifest --check",
        "python scripts\\release.py verify",
        "npm pack --dry-run --json",
        "read-only github community profile baseline",
        "local public-checkout sync only",
        "no live community-profile improvement",
        "no push, tag, release, registry, settings, discussions, labels, branch protection, or system update",
    ):
        assert phrase in checklist


def test_release_checklist_documents_phase28_ci_visibility_gates() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 28 release automation, provenance, and ci visibility",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
        ".github/dependabot.yml",
        "docs/ci-and-release-policy.md",
        "tests/test_workflow_safety.py",
        "python -m pytest tests\\test_workflow_safety.py",
        "python scripts\\quality.py",
        "python scripts\\release.py manifest --check",
        "python scripts\\release.py verify",
        "npm pack --dry-run --json",
        "gitleaks dir . --no-banner --redact",
        "quality",
        "security",
        "python `3.11` and `3.12`",
        "node.js `24`",
        "committed codeql advanced setup",
        "fail-on-severity: high",
        "weekly grouped",
        "open pr limit 5",
        "contents: read",
        "security-events: write",
        "packages: write",
        "id-token: write",
        "attestations: write",
        "release please",
        "semantic-release",
        "conventional commits",
        "source-release manifest metadata",
        "excluded from npm package contents",
    ):
        assert phrase in checklist


def test_release_checklist_documents_phase29_registry_strategy_gates() -> None:
    checklist = _checklist_text()

    for phrase in (
        "phase 29 registry publication strategy",
        "docs/registry-publication-strategy.md",
        "github releases are the current source-only public channel",
        "`v0.1.0` remains github-source-only",
        "pypi is the primary future python registry",
        "testpypi is required for the first registry release",
        "npm is a public thin-launcher channel",
        "github packages remains deferred",
        "python -m pytest tests\\test_registry_publication_strategy.py",
        "python scripts\\release.py manifest --check",
        "python scripts\\release.py verify",
        "npm pack --dry-run --json",
        "npm view linkedin-apply-assistant version --json",
        "https://pypi.org/pypi/linkedin-apply-assistant/json",
        "https://test.pypi.org/pypi/linkedin-apply-assistant/json",
        "gh release list --repo mohammedghazal09/linkedin-apply-assistant",
        "repository",
        "version",
        "channel",
        "workflow or manual action owner",
        "exact mutation",
        "python -m build",
        "twine check dist/*",
        "local wheel install smoke",
        "package contents inspection",
        "gitleaks or release scan",
        "pypi trusted publishing",
        "github actions oidc",
        "npm trusted publishing",
        "no shared long-lived registry tokens",
        "protected environments such as `testpypi`, `pypi`, and `npm`",
        "future `release.yml` identity only after explicit approval",
        "no `packages: write`, `id-token: write`, or `attestations: write` in phase 29",
        "no executable registry rollback script",
    ):
        assert phrase in checklist


def test_release_checklist_documents_v011_npm_and_powershell_release() -> None:
    checklist = _checklist_text()

    for phrase in (
        "v0.1.1 npm and powershell distribution release",
        "downloadable through npm and a no-admin powershell installer",
        "package version: `0.1.1`",
        "npm package: `linkedin-apply-assistant`",
        "npm dist-tag: `latest`",
        "powershell installer: `install.ps1`",
        "pypi and testpypi remain future channels",
        "tests\\test_distribution_metadata.py tests\\test_docs_smoke.py tests\\test_npm_launcher.py",
        "npm pack --dry-run --json",
        "psparser",
        "npm view linkedin-apply-assistant version --json",
        "npm view linkedin-apply-assistant dist-tags --json",
        "linkedin-apply-assistant@0.1.1",
        "the launcher has no hidden install or registry publish code",
        "`install.ps1` downloads from the public github source archive",
        "does not use `invoke-expression`",
        "pyPI and testpypi uploads stay out of this release".lower(),
        "`v0.1.0` remains source-only",
    ):
        assert phrase in checklist


def test_release_checklist_documents_v012_install_docs_patch_release() -> None:
    checklist = _checklist_text()

    for phrase in (
        "v0.1.2 install documentation simplification release",
        "one npm command",
        "one direct powershell installer command",
        "package version: `0.1.2`",
        "github release: `v0.1.2`",
        "runtime behavior, browser safety posture, and public cli contract are unchanged",
        "tests\\test_distribution_metadata.py tests\\test_docs_smoke.py",
        "npm pack --dry-run --json",
        "npm view linkedin-apply-assistant version --json",
        "npm view linkedin-apply-assistant dist-tags --json",
        "gh release view v0.1.2",
        "docs-only package refresh",
        "immutable npm readme",
        "no lifecycle install, publish, or token scripts",
        "avoid `invoke-expression`",
        "pypi and testpypi uploads stay out of this release",
    ):
        assert phrase in checklist


def test_release_checklist_documents_v013_short_powershell_release() -> None:
    checklist = _checklist_text()

    for phrase in (
        "v0.1.3 powershell short installer command release",
        "irm https://raw.githubusercontent.com/mohammedghazal09/linkedin-apply-assistant/main/install.ps1 | iex",
        "package version: `0.1.3`",
        "github release: `v0.1.3`",
        "runtime behavior, browser safety posture, and public cli contract are unchanged",
        "longer temp-file powershell installer form remains documented",
        "tests\\test_distribution_metadata.py tests\\test_docs_smoke.py",
        "npm pack --dry-run --json",
        "npm view linkedin-apply-assistant version --json",
        "npm view linkedin-apply-assistant dist-tags --json",
        "gh release view v0.1.3",
        "docs-only package refresh",
        "immutable npm readme",
        "no lifecycle install, publish, or token scripts",
        "`install.ps1` itself is unchanged",
        "pypi and testpypi uploads stay out of this release",
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
