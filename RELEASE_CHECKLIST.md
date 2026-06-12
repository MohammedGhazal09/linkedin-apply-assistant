# Release Checklist

Use this checklist before publishing LinkedIn-apply-assistant.

## Phase 19 No-Publish Workflow

Phase 19 is release readiness only. It does not create a remote, push code, create tags, create a GitHub Release, publish to npm, or publish to PyPI.

The release target is a future clean standalone repository containing only the public files from `standalone/linkedin-apply-assistant`. The future public repository uses `main` as its default branch.

The future first tag is `v0.1.0` only after Phases 20 and 21 pass and explicit ship approval is given. Phase 20 owns download and install paths for npm and source code. Phase 21 owns terminal usage polish and first-run command help.

Release notes come from package `CHANGELOG.md` plus Phase 19 evidence in `.planning/phases/19-prepare-clean-public-release-repository-and-private-data-qua/19-VERIFICATION.md`.

Manual approval point: stop before any `gh repo create`, `git remote add`, `git push`, `git tag`, GitHub Release, npm publish, or PyPI publish action. Approval must name the target repository and release channel.

Rollback path for failed readiness: delete the generated candidate or archive, do not reuse the failed candidate, rerun `python scripts\release.py clean`, then rerun `python scripts\release.py verify`.

Use specific-file staging only, for example:

```powershell
git add -- RELEASE_CHECKLIST.md CHANGELOG.md scripts\release.py release-manifest.json
git add -- docs\install-and-configuration.md docs\troubleshooting.md README.md
```

Do not add `docs/publishing.md` in Phase 19.

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
| Terminal help drift | `python -m pytest tests\test_cli_help.py tests\test_config_diagnostics.py -q` confirms root help, subcommand help, and `linkedin-apply-assistant config check` stay actionable. | Pending release review |
| Config diagnostics drift | `tests\test_config_diagnostics.py` confirms `config check` reports runtime paths without creating workspace files or directories. | Pending release review |
| Command reference drift | `docs\commands.md` remains linked from README and install docs, and docs smoke checks keep command coverage current. | Pending release review |
| Browser setup guidance drift | Help and docs keep `python -m playwright install chromium`, browser profile guidance, no-submit language, and browser submission remains disabled. | Pending release review |
| Explicit no-publish approval | Stop before any remote, tag, GitHub Release, registry token setup, npm registry action, PyPI registry action, or TestPyPI registry action until explicit ship approval names the target channel. | Pending release review |

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
- `package.json` omits `repository`, `homepage`, and `bugs` until the real standalone public repository exists.

## Verification Commands

From the package root:

```powershell
python -m pytest tests\test_cli_help.py tests\test_config_diagnostics.py -q
python -m pytest tests\test_docs_smoke.py tests\test_npm_launcher.py tests\test_distribution_metadata.py tests\test_distribution_smoke.py tests\test_release_manifest.py tests\test_release_readiness.py -q
python -m build --outdir $env:TEMP\linkedin-apply-assistant-dist
npm pack --dry-run --json
python scripts\release.py clean
python scripts\release.py manifest --check
python scripts\release.py verify
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
