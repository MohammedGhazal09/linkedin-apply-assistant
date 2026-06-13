# Changelog

All notable package-local changes are documented here.

This file follows the spirit of Keep a Changelog and uses semantic version labels where available.

## [Unreleased]

### Added

- Community health files and contribution templates for the standalone public
  repository package surface.
- Registry publication strategy covering GitHub source releases, future PyPI,
  TestPyPI, npm launcher, and deferred GitHub Packages channels without
  changing package version or publishing to a registry.

## [0.1.0] - 2026-06-12

### Added

- Initial GitHub source release for the standalone `linkedin-apply-assistant` package.
- Fresh-reader package README and user-journey docs.
- Package-local legal, security, contribution, migration, release checklist, license, and third-party notice docs.
- Synthetic report examples and release-readiness verification coverage.
- Source, Python, and npm launcher install path readiness for local validation without registry publication.
- Distribution metadata, Python build, npm pack, and release-manifest smoke coverage for version `0.1.0`.
- Terminal help, read-only config diagnostics, command reference docs, and release-readiness coverage for Phase 21 terminal UX.
- Public GitHub metadata and release-readiness documentation for PUB-07.
- Initial standalone package boundary for local LinkedIn job workflows.
- Console command `linkedin-apply-assistant` with `search`, `assist`, `apply`, `dry-run`, and `report`.
- Sanitized config, Q&A bank, and dry-run input examples.
- Package-local quality gate with pytest, Ruff, compile checks, and dependency audit.
- No-submit safety posture and visible-browser workflow boundaries.
- User-controlled source install and download path through the canonical GitHub repository.
- Release hygiene covering manifest verification, local build/pack smoke tests, and gitleaks evidence.
- GitHub source release scope only; no npm, PyPI, or TestPyPI registry package is part of this release.
