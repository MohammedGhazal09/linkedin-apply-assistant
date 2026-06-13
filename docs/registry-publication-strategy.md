# Registry Publication Strategy

Status: strategy only. This document does not publish a package, reserve a
package name, configure a trusted publisher, create a registry token, log in to
a registry, create a tag, upload a GitHub Release asset, or grant publish-capable
workflow permissions.

The current public release channel is GitHub source releases only. The first
GitHub source release, `v0.1.0`, remains source-only and is not a registry
backfill candidate.

## Current Boundary

- Current package metadata version: `0.1.0`.
- Current install path: source checkout, local Python install, local editable
  install, and local npm launcher dry-run validation.
- Current public channel: GitHub repository source checkout and GitHub source
  release archives.
- Not current: PyPI package, TestPyPI package, npm package, GitHub Packages
  package, trusted-publisher setup, package-name reservation, registry tokens,
  registry login, release asset uploads, artifact attestations, provenance, or
  signing.

Registry install commands remain future commands until a later phase explicitly
approves the target registry, version, repository, workflow or manual action,
and exact mutation.

## Channel Matrix

| Channel | Current status | Future status | Rationale | Prerequisites | Publish trigger | Verification | Rollback or remediation |
|---|---|---|---|---|---|---|---|
| GitHub Releases | Current source-only channel for `v0.1.0`. No wheel, sdist, npm tarball, or other release asset is attached. | Keep as the source-of-truth release record. Future assets require explicit approval. | Users can inspect and install from source without introducing registry auth or package-name ownership. | Clean local verification, changelog, release checklist, source manifest, approved tag or release mutation. | Explicit GitHub Release approval naming repo, tag, target commit, release state, and assets, if any. | `gh release view`, `gh release list`, source archive inspection, release manifest verification. | Remove mistaken assets from the release, correct the release notes, or delete a draft. Source tags need separate explicit remediation because asset removal does not undo a tag. |
| PyPI | Not published and not reserved. | Primary future registry for real package publication. | The project is a Python CLI with Playwright-driven browser automation, so PyPI is the natural install path. | Maintainer or maintainer-controlled organization ownership, account 2FA where supported, PyPI Trusted Publishing with GitHub Actions OIDC, protected `pypi` environment, clean build and metadata gates. | Explicit PyPI approval naming repository, version, PyPI project, workflow or manual action, and exact upload mutation. | Read-only JSON API check, `python -m build`, `twine check dist/*`, local wheel install smoke, release scan, manifest verification. | Prefer yanking a broken release where appropriate. Deletion is disruptive and permanent; never rely on deleting and reusing the same version. |
| TestPyPI | Not published and not reserved. | Required preflight for the first registry release and for publish-workflow changes. Routine patch preflights can become optional only after a proven release cycle. | It exercises package metadata, artifacts, and installer behavior before the real PyPI release. | Same artifact gates as PyPI, protected `testpypi` environment, explicit preflight approval, no production token. | Explicit TestPyPI approval naming repository, version, TestPyPI project, workflow or manual action, and exact upload mutation. | TestPyPI JSON API check, metadata validation, test-index install smoke, package contents review. | Clean up mistaken TestPyPI releases where possible and move forward with a new version if needed. Do not treat TestPyPI cleanup as production rollback proof. |
| npm | Not published and not reserved. | Secondary future thin-launcher channel. | npm can provide a familiar global command, but the launcher delegates to the Python CLI and does not install Python or Playwright for the user. | Maintainer or maintainer-controlled ownership, account 2FA where supported, npm trusted publishing or OIDC where supported, protected `npm` environment, exact package contents review. | Explicit npm approval naming repository, version, npm package, workflow or manual action, and exact registry mutation. | `npm pack --dry-run --json`, package contents inspection, no lifecycle install/publish scripts, npm read-only registry check. | Prefer deprecation for bad packages when unpublish criteria are not met. A used npm `package@version` cannot be reused, even after unpublish. |
| GitHub Packages | Not used. | Deferred. | It adds `packages: write` and authenticated consumption friction without improving the primary Python install path. | A future reason to publish a package to GitHub Packages, explicit package type, permission model, and install documentation. | Separate approval naming package type, repository, version, and exact mutation. | GitHub Packages read-only checks and package permission review. | Delete or deprecate only according to the package type's GitHub Packages support. This is not a substitute for PyPI/npm remediation. |

## Package Names

The target package name for future PyPI, TestPyPI, and npm publication is
`linkedin-apply-assistant`.

If the unscoped npm name is unavailable later, the fallback is a future scoped
npm package under a maintainer-controlled scope. Phase 29 does not reserve names
or create registry projects.

## Version Sequencing

- `v0.1.0` stays a GitHub source-only release.
- No registry should backfill `0.1.0`.
- The first registry release must use a later explicitly approved package version.
- If only registry documentation and publication gates change, the default
  future version example is `0.1.1`.
- If user-visible behavior changes before registry publication, the default
  future version example is `0.2.0`.
- The actual version is a SemVer policy decision at the future publish phase,
  not a Phase 29 version bump.

## Ownership and Authentication

Future registry publication must use maintainer-owned or maintainer-controlled
organization accounts.

Required future controls:

- Account 2FA where the registry supports it.
- PyPI Trusted Publishing with GitHub Actions OIDC for PyPI/TestPyPI.
- npm trusted publishing or equivalent OIDC flow where supported.
- Protected GitHub environments such as `testpypi`, `pypi`, and `npm`.
- A tightly scoped future release workflow identity, commonly `release.yml`, but
  no release workflow is added in Phase 29.
- No shared long-lived registry tokens.
- No publish credentials in repository files, examples, local configs, or
  package metadata.

Future OIDC and attestation work may require permissions such as
`id-token: write`, `attestations: write`, or `packages: write`. Phase 29 does not grant those permissions.

## Future Publish Gates

Every future registry publication approval must include fresh evidence for the
target version:

- Python build: `python -m build`.
- Python metadata validation: `twine check dist/*`.
- Local wheel install smoke from a temporary output directory.
- npm launcher package dry run: `npm pack --dry-run --json`.
- Package contents inspection for source release and npm package surfaces.
- Release manifest check: `python scripts\release.py manifest --check`.
- Release verification: `python scripts\release.py verify`.
- Secret scan or release scan with gitleaks or the package release scanner.
- Read-only npm, PyPI, and TestPyPI registry version or absence checks.
- GitHub Release read-only checks when source tags or release assets are in
  scope.

Live registry checks stay out of default pytest and CI. They are verification
commands for the human-approved release step.

## Approval Templates

Use these templates verbatim in a future approval message before any registry or
release mutation.

### TestPyPI Preflight

- Repository: `MohammedGhazal09/linkedin-apply-assistant`
- Version: `<version>`
- Channel: TestPyPI
- Workflow or manual action: `<workflow filename or manual command owner>`
- Exact mutation: upload the verified sdist and wheel for `<version>` to
  TestPyPI only.

### PyPI Release

- Repository: `MohammedGhazal09/linkedin-apply-assistant`
- Version: `<version>`
- Channel: PyPI
- Workflow or manual action: `<workflow filename or manual command owner>`
- Exact mutation: upload the verified sdist and wheel for `<version>` to PyPI.

### npm Launcher Release

- Repository: `MohammedGhazal09/linkedin-apply-assistant`
- Version: `<version>`
- Channel: npm
- Workflow or manual action: `<workflow filename or manual command owner>`
- Exact mutation: publish the verified npm launcher package for `<version>` to
  the npm public registry.

### GitHub Release Asset Work

- Repository: `MohammedGhazal09/linkedin-apply-assistant`
- Version or tag: `<version-or-tag>`
- Channel: GitHub Releases
- Workflow or manual action: `<workflow filename or manual command owner>`
- Exact mutation: upload, replace, or remove the named release asset(s) for
  `<version-or-tag>`.

## Rollback and Remediation Notes

- PyPI: prefer yanking for broken releases where appropriate. Deletion is
  disruptive and should not be treated as a normal rollback path.
- TestPyPI: cleanup is acceptable for preflight mistakes, but it does not prove
  production rollback.
- npm: unpublish is limited and irreversible in important ways; deprecation is often the safer remediation path. A used package version cannot be reused.
- GitHub Releases: removing a release asset does not remove source archives,
  tags, or downstream copies. Tag remediation requires a separate explicit
  approval.

Do not add executable rollback scripts for registry actions until a future phase
has a concrete approved publication mechanism.

## Related Docs

- [Install and configuration](install-and-configuration.md)
- [CI and release policy](ci-and-release-policy.md)
- [Release checklist](../RELEASE_CHECKLIST.md)
