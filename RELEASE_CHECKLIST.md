# Release Checklist

Use this checklist before publishing LinkedIn-apply-assistant.

## Phase 23 PUB-07 Public Metadata Readiness

PUB-07 confirms that package metadata, source-install docs, and release hygiene point to the canonical public repository:

```text
https://github.com/MohammedGhazal09/linkedin-apply-assistant
```

This checklist is release readiness only. It does not create tags, create a GitHub Release, publish to npm, publish to PyPI, publish to TestPyPI, configure registry tokens, or run registry provenance automation.

The future first tag is `v0.1.0` only after Phase 24 and explicit release approval. Phase 22 created and verified the public repository. Phase 23 owns public metadata and release-tooling readiness. Phase 24 owns tag and GitHub Release creation.

Release notes come from package `CHANGELOG.md` plus Phase 23 evidence in `.planning/phases/23-finalize-public-metadata-and-release-tooling-pub-07/23-VERIFICATION.md`.

Manual approval point: stop before any `git push`, `git tag`, GitHub Release, npm publish, PyPI publish, TestPyPI publish, registry-token setup, public-visibility change, or other external action not explicitly authorized for the current phase. Approval must name the target repository or release channel.

Rollback path for failed readiness: delete the generated candidate or archive, do not reuse the failed candidate, rerun `python scripts\release.py clean`, then rerun `python scripts\release.py verify`.

Use specific-file staging only, for example:

```powershell
git add -- RELEASE_CHECKLIST.md CHANGELOG.md scripts\release.py release-manifest.json
git add -- docs\install-and-configuration.md docs\troubleshooting.md README.md
```

Do not add registry-publish automation in PUB-07.

## Phase 24 PUB-08 v0.1.0 GitHub Source Release

PUB-08 publishes the first GitHub source release only:

- Repository: `MohammedGhazal09/linkedin-apply-assistant`
- Tag: `v0.1.0`
- Release type: draft-first GitHub Release, then final/latest only after verification passes.
- Package scope: source checkout, generated GitHub source archives, and local build/pack smoke evidence.
- Safety boundary: browser workflows remain user-controlled and no-submit; the package prepares and assists, but does not click final application submission for the user.

Explicit ship approval is required before any of these actions:

- pushing the verified release-prep `main` commit to `origin/main`
- annotated tag creation for `v0.1.0`
- then pushing only `refs/tags/v0.1.0` for the tag step
- draft GitHub Release creation with `--verify-tag`
- final publication after draft/source verification

Required Phase 24 evidence:

- Release-prep main sync: `git -C W:\linkedin-apply-assistant-public status --short --branch`, `git -C W:\linkedin-apply-assistant-public rev-parse HEAD`, `git -C W:\linkedin-apply-assistant-public push origin main`, and `git -C W:\linkedin-apply-assistant-public ls-remote --heads origin main` confirm `origin/main` matches the verified release-prep commit before tag creation.
- Focused release/docs tests: `python -m pytest tests\test_distribution_metadata.py tests\test_release_readiness.py`
- Full package quality gate: `python scripts\quality.py`
- Clean release workspace: `python scripts\release.py clean`
- Manifest verification: `python scripts\release.py manifest --check`
- Release scan: `python scripts\release.py verify`
- Python build smoke outside the package root: `python -m build --outdir <temp>`
- npm launcher smoke without registry upload: `npm pack --dry-run --json`
- Real gitleaks evidence: `gitleaks version`, package directory scan, public checkout directory scan, and public checkout history scan all pass with `gitleaks: passed`
- Draft release check: `gh release view v0.1.0 --repo MohammedGhazal09/linkedin-apply-assistant --json tagName,name,url,isDraft,isPrerelease,targetCommitish,zipballUrl,tarballUrl,assets`
- Release list check: `gh release list --repo MohammedGhazal09/linkedin-apply-assistant --json tagName,name,isDraft,isLatest,isPrerelease,publishedAt --limit 20`
- No-registry proof: npm and PyPI read-only absence checks remain package-not-found or 404 before and after the GitHub source release.

No-registry and no-asset boundary:

- no npm publish
- no PyPI publish
- no TestPyPI publish
- no registry token setup
- empty release assets on GitHub; do not attach wheel, sdist, or npm tarball artifacts
- no provenance, attestations, branch protection, topics, Release Please, or repository-hardening work in this phase
- no broad branch, mirror, or all-tags push; the only branch update in PUB-08 is the explicitly approved release-prep `main` push before tag creation

Rollback commands for failed draft/tag work:

```powershell
gh release delete v0.1.0 --repo MohammedGhazal09/linkedin-apply-assistant --yes --cleanup-tag
git -C W:\linkedin-apply-assistant-public push origin :refs/tags/v0.1.0
git -C W:\linkedin-apply-assistant-public tag -d v0.1.0
```

## Phase 26 Community Health Files and Contribution Templates

Phase 26 prepares community-health files and contribution templates for local
review only. It does not push, tag, create a release, publish to a registry,
change repository settings, enable Discussions, edit labels, change branch
protection, or apply a system update.

No push, tag, release, registry, settings, Discussions, labels, branch protection, or system update is allowed in Phase 26.

Required files/templates:

- `SUPPORT.md`
- `GOVERNANCE.md`
- `CODE_OF_CONDUCT.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/docs.yml`
- `.github/ISSUE_TEMPLATE/safety_compliance.yml`
- `.github/ISSUE_TEMPLATE/config_help.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`

Required Phase 26 evidence:

```powershell
python -m pytest tests\test_community_health.py tests\test_docs_smoke.py tests\test_privacy_scans.py tests\test_npm_launcher.py tests\test_distribution_smoke.py tests\test_release_manifest.py tests\test_release_readiness.py -q
python scripts\release.py manifest --check
python scripts\release.py verify
npm pack --dry-run --json
gh api repos/MohammedGhazal09/linkedin-apply-assistant/community/profile --jq '.health_percentage'
```

Community-health release gate:

- focused community-health tests pass
- docs smoke checks cover support, governance, conduct, issue template, and PR
  template links
- privacy scan coverage includes root community docs and `.github` templates
- `release-manifest.json` includes root community docs, issue forms, PR
  template, and `tests/test_community_health.py`
- npm dry-run includes the same community docs/templates expected from
  `package.json` files
- read-only GitHub community profile baseline is recorded before any push
- local public-checkout sync only; no live community-profile improvement is
  claimed until a later approved push publishes the files

## Phase 28 Release Automation, Provenance, and CI Visibility

Phase 28 adds CI visibility and release-policy documentation. It does not
publish packages, create or mutate tags, create or mutate GitHub Releases,
reserve package names, configure trusted publishers, enable artifact
attestations, create SBOM artifacts, add signing keys, or mutate branch rulesets,
tag rulesets, required checks, labels, assignees, or repository settings.

Required files:

- `.github/workflows/quality.yml`
- `.github/workflows/security.yml`
- `.github/dependabot.yml`
- `docs/ci-and-release-policy.md`
- `tests/test_workflow_safety.py`

Required Phase 28 local evidence:

```powershell
python -m pytest tests\test_workflow_safety.py tests\test_docs_smoke.py tests\test_distribution_metadata.py tests\test_release_manifest.py tests\test_release_readiness.py tests\test_quality_gate.py -q
python scripts\quality.py
python scripts\release.py clean
python scripts\release.py manifest --check
python scripts\release.py verify
npm pack --dry-run --json
gitleaks version
gitleaks dir . --no-banner --redact
```

Required Phase 28 public verification after explicit sync approval:

```powershell
gh api repos/MohammedGhazal09/linkedin-apply-assistant/actions/workflows --jq ".workflows[] | {name,path,state,id}"
gh workflow list --repo MohammedGhazal09/linkedin-apply-assistant
gh run list --repo MohammedGhazal09/linkedin-apply-assistant --limit 10
gh api repos/MohammedGhazal09/linkedin-apply-assistant/dependabot/alerts --paginate --jq "length"
gh release list --repo MohammedGhazal09/linkedin-apply-assistant --limit 10
git ls-remote --tags origin
```

CI and release-policy gate:

- only two user-authored workflow badges are added: `Quality` and `Security`
- badge URLs point at the `main` branch and the user-authored workflow files
- `Quality` runs Python `3.11` and `3.12` on Ubuntu and a single Node.js `24`
  release-smoke lane
- `Security` runs committed CodeQL advanced setup for Python and JavaScript,
  Dependency Review with `fail-on-severity: high`, and Gitleaks secret scanning
- Dependabot covers GitHub Actions, npm, and pip at `/` with weekly grouped
  updates, open PR limit 5, no auto-merge, and no labels or assignees
- workflow permissions default to `contents: read`
- `security-events: write` is allowed only for the CodeQL job
- no `packages: write`, `id-token: write`, or `attestations: write`
- no Release Please, semantic-release, or equivalent tag/release automation
- Conventional Commits are advisory documentation only and are not enforced in CI
- workflows and Dependabot config are source-release manifest metadata, but are
  excluded from npm package contents unless a future phase intentionally changes
  that policy

## Phase 29 Registry Publication Strategy

Phase 29 documents the package-channel decision and static registry policy. It
does not publish packages, reserve package names, create registry projects,
configure trusted publishers, create registry tokens, log in to registries,
create or mutate tags, create or mutate GitHub Releases, upload release assets,
grant publish-capable workflow permissions, or apply a career-ops system update.

Canonical strategy doc:

- `docs/registry-publication-strategy.md`

Channel decision:

- GitHub Releases are the current source-only public channel.
- `v0.1.0` remains GitHub-source-only and is not a registry backfill candidate.
- PyPI is the primary future package registry.
- TestPyPI is required for the first registry release and publish-workflow
  changes.
- npm is a secondary future thin-launcher channel that delegates to the Python
  CLI.
- GitHub Packages remains deferred.

Required Phase 29 local evidence:

```powershell
python -m pytest tests\test_registry_publication_strategy.py tests\test_docs_smoke.py tests\test_distribution_metadata.py tests\test_release_readiness.py tests\test_release_manifest.py tests\test_npm_launcher.py tests\test_distribution_smoke.py tests\test_workflow_safety.py -q
python scripts\quality.py
python scripts\release.py clean
python scripts\release.py manifest --check
python scripts\release.py verify
npm pack --dry-run --json
```

Required Phase 29 read-only absence checks:

```powershell
npm view linkedin-apply-assistant version --json
try { (Invoke-WebRequest -UseBasicParsing https://pypi.org/pypi/linkedin-apply-assistant/json -TimeoutSec 20).StatusCode } catch { $_.Exception.Response.StatusCode.value__ }
try { (Invoke-WebRequest -UseBasicParsing https://test.pypi.org/pypi/linkedin-apply-assistant/json -TimeoutSec 20).StatusCode } catch { $_.Exception.Response.StatusCode.value__ }
gh release list --repo MohammedGhazal09/linkedin-apply-assistant --limit 5
gh workflow list --repo MohammedGhazal09/linkedin-apply-assistant
```

Future registry approval must name:

- repository
- version
- channel
- workflow or manual action owner
- exact mutation

Future gate categories:

- Python build with `python -m build`
- Python metadata validation with `twine check dist/*`
- local wheel install smoke
- npm dry-run with `npm pack --dry-run --json`
- package contents inspection
- manifest verification with `python scripts\release.py manifest --check`
- release verification with `python scripts\release.py verify`
- gitleaks or release scan
- read-only npm, PyPI, and TestPyPI registry checks

Future registry security boundary:

- maintainer or maintainer-controlled organization ownership
- account 2FA where supported
- PyPI Trusted Publishing with GitHub Actions OIDC
- npm trusted publishing or OIDC where supported
- protected environments such as `testpypi`, `pypi`, and `npm`
- no shared long-lived registry tokens
- future `release.yml` identity only after explicit approval
- no `packages: write`, `id-token: write`, or `attestations: write` in Phase 29

Future approval templates are in `docs/registry-publication-strategy.md` for:

- TestPyPI preflight
- PyPI release
- npm launcher release
- GitHub Release asset work

Rollback and remediation policy:

- PyPI: prefer yanking where appropriate; deletion is disruptive.
- TestPyPI: cleanup is preflight-only and not production rollback proof.
- npm: deprecation is often safer than unpublish, and used package versions
  cannot be reused.
- GitHub Releases: asset removal does not undo source archives or tags.
- no executable registry rollback script is part of Phase 29.

## Required Public Metadata

`package.json` must include exactly these public project fields:

- `repository.type`: `git`
- `repository.url`: `git+https://github.com/MohammedGhazal09/linkedin-apply-assistant.git`
- `homepage`: `https://github.com/MohammedGhazal09/linkedin-apply-assistant#readme`
- `bugs.url`: `https://github.com/MohammedGhazal09/linkedin-apply-assistant/issues`

`pyproject.toml` must include exactly these project URLs:

- `Homepage`: `https://github.com/MohammedGhazal09/linkedin-apply-assistant#readme`
- `Repository`: `https://github.com/MohammedGhazal09/linkedin-apply-assistant`
- `Issues`: `https://github.com/MohammedGhazal09/linkedin-apply-assistant/issues`

## Hard Publish Blockers

| Blocker | Required evidence | Status |
|---|---|---|
| Missing license | `LICENSE` exists in package root. | Pending release review |
| Missing notices | `THIRD_PARTY_NOTICES.md` includes Career-Ops attribution where required and Scrapling BSD 3-Clause notice. | Pending release review |
| Private-data leaks | Privacy/static scans pass and examples remain synthetic. | Pending release review |
| Stale commands | Docs smoke checks cover `search`, `assist`, `apply`, `dry-run`, `report`, and shared flags. | Pending release review |
| Unsafe submit wording | Docs preserve no-submit and prepare-only apply language. | Pending release review |
| Failing package quality/docs/privacy scans | `python scripts\quality.py` passes from package root. | Pending release review |
| Missing Phase 17 verification evidence | `.planning/phases/17-build-reproducible-test-harness-ci-and-quality-gates/17-VERIFICATION.md` exists and records passing package quality, package pytest, root smoke, docs smoke, privacy scans, Ruff, dependency audit, and live-test exclusion. | Verified locally before Phase 18 |
| Top-level generated artifacts after verification | Package root has no top-level `.pytest_cache`, `.ruff_cache`, `build/`, or `dist/` after quality/docs/privacy checks. This is the automated post-quality artifact gate. | Pending release review |
| Final packaging cleanup | Before creating a distribution archive, recursive final-clean inspection finds no `.pytest_cache`, `.ruff_cache`, `__pycache__`, `*.egg-info`, `build/`, or `dist/` publish blockers. `__pycache__` and editable-install metadata can appear during normal verification, so this is a final publish gate. | Pending release review |
| Distribution metadata drift | `python -m pytest tests\test_distribution_metadata.py -q` confirms Python, npm, docs, changelog, and release checklist names/versions stay synchronized. | Pending release review |
| Python build smoke | `python -m build --outdir <temp>` creates local sdist and wheel artifacts outside the package root. | Pending release review |
| npm pack smoke | `npm pack --dry-run --json` reports the package-local npm launcher shape without sending anything to a registry. | Pending release review |
| npm launcher guardrails | `python -m pytest tests\test_npm_launcher.py tests\test_distribution_smoke.py -q` confirms the launcher delegates to Python and has no hidden install or registry action. | Pending release review |
| Public metadata drift | `python -m pytest tests\test_distribution_metadata.py tests\test_npm_launcher.py -q` confirms npm and Python metadata point to the canonical GitHub repository. | Pending release review |
| Public source docs drift | `python -m pytest tests\test_docs_smoke.py tests\test_release_readiness.py -q` confirms source checkout docs use the canonical GitHub repository and registry/tag/release wording remains pending. | Pending release review |
| Missing community health files | `python -m pytest tests\test_community_health.py tests\test_docs_smoke.py tests\test_privacy_scans.py -q`, `python scripts\release.py manifest --check`, and `npm pack --dry-run --json` confirm support, governance, conduct, issue forms, PR template, privacy warnings, release manifest, and npm package inclusion. | Pending release review |
| Real gitleaks evidence | `gitleaks version`, `python scripts\release.py verify`, and `python scripts\release.py scan <candidate-or-checkout>` record real gitleaks scans with `gitleaks: passed`. | Pending release review |
| Terminal help drift | `python -m pytest tests\test_cli_help.py tests\test_config_diagnostics.py -q` confirms root help, subcommand help, and `linkedin-apply-assistant config check` stay actionable. | Pending release review |
| Config diagnostics drift | `tests\test_config_diagnostics.py` confirms `config check` reports runtime paths without creating workspace files or directories. | Pending release review |
| Command reference drift | `docs\commands.md` remains linked from README and install docs, and docs smoke checks keep command coverage current. | Pending release review |
| Browser setup guidance drift | Help and docs keep `python -m playwright install chromium`, browser profile guidance, no-submit language, and browser submission remains disabled. | Pending release review |
| Explicit no-publish approval | Stop before any remote, tag, GitHub Release, registry token setup, npm registry action, PyPI registry action, or TestPyPI registry action until explicit ship approval names the target channel. | Pending release review |
| No-publish proof | Confirm no npm package, no PyPI project, no `v0.1.0` tag, and no GitHub Release `v0.1.0` exist unless a later approved phase created them. | Pending release review |

Do not publish while any hard blocker remains unresolved.

## Advisory Checklist

- README explains purpose, install, commands, safety boundary, and docs map.
- `docs/` covers install/configuration, visible-browser session setup, search-only, assistive fill-only, prepare-only apply, report review, and troubleshooting.
- Examples cover config, Q&A bank, dry-run input, and synthetic report shape.
- `LEGAL.md` and `SAFETY.md` remain linked from README.
- `MIGRATION.md` explains extraction scope and excluded root surfaces.
- `CONTRIBUTING.md` and `SECURITY.md` are standalone-scoped.
- Changelog has `Unreleased` and `0.1.0`.
- Source, Python, and npm launcher install docs are current and tested.
- Phase 21 terminal UX docs and help stay current: `docs\commands.md`, `tests\test_cli_help.py`, and `tests\test_config_diagnostics.py`.
- Public package metadata points to the canonical GitHub repository and issue tracker.
- Community health files and contribution templates are included in package and release checks.

## Verification Commands

From the package root:

```powershell
python -m pytest tests\test_cli_help.py tests\test_config_diagnostics.py -q
python -m pytest tests\test_docs_smoke.py tests\test_npm_launcher.py tests\test_distribution_metadata.py tests\test_distribution_smoke.py tests\test_release_manifest.py tests\test_release_readiness.py -q
python -m pytest tests\test_community_health.py tests\test_docs_smoke.py tests\test_privacy_scans.py tests\test_npm_launcher.py tests\test_distribution_metadata.py tests\test_distribution_smoke.py tests\test_release_manifest.py tests\test_release_readiness.py -q
python -m build --outdir $env:TEMP\linkedin-apply-assistant-dist
npm pack --dry-run --json
gitleaks version
python scripts\release.py clean
python scripts\release.py manifest --check
python scripts\release.py verify
python scripts\release.py scan .
python scripts\quality.py
python -m pytest tests -q
```

From the repository root:

```powershell
node test-all.mjs --quick
```

Automated post-quality artifact scan:

```powershell
Get-ChildItem standalone\linkedin-apply-assistant -Force | Where-Object { $_.Name -in '.pytest_cache','.ruff_cache','build','dist' -or $_.Name -like '*.egg-info' }
```

Final packaging cleanup inspection:

```powershell
Get-ChildItem standalone\linkedin-apply-assistant -Force -Recurse | Where-Object {
  $_.Name -in '.pytest_cache','.ruff_cache','build','dist','__pycache__' -or
  $_.Name -like '*.egg-info'
}
```
