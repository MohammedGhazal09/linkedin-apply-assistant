# Changelog

All notable package-local changes are documented here.

This file follows the spirit of Keep a Changelog and uses semantic version labels where available.

## [Unreleased]

## [0.1.4] - 2026-06-13

### Fixed

- Made `linkedin-apply-assistant --verbose` print root help and a first-run hint
  instead of failing with a missing `command` parser error.
- Made `linkedin-apply-assistant config` default to the read-only
  `config check` diagnostics command instead of failing with a missing
  `config_command` parser error.

## [0.1.3] - 2026-06-13

### Changed

- Replaced the README and npm package-page PowerShell installer command with
  the shorter `irm ... | iex` form.
- Kept the inspectable temp-file PowerShell installer form in the detailed
  install guide for optional installer arguments.

## [0.1.2] - 2026-06-13

### Changed

- Simplified README and npm package-page install instructions to one npm
  command plus one direct PowerShell installer command.
- Kept extended Python, Playwright, source checkout, and troubleshooting details
  in the canonical install guide instead of duplicating them in the README.

## [0.1.1] - 2026-06-13

### Added

- Community health files and contribution templates for the standalone public
  repository package surface.
- Registry publication strategy covering GitHub source releases, PyPI,
  TestPyPI, npm launcher, PowerShell installer, and deferred GitHub Packages
  channels.
- NPM global launcher release path for `linkedin-apply-assistant`.
- PowerShell no-admin installer that downloads the public GitHub source archive,
  creates a local virtual environment, writes command shims, and can optionally
  install Playwright Chromium.

### Changed

- NPM package contents now include `pyproject.toml`, `src/`, and `install.ps1`
  so the global launcher can point users at the bundled Python package.

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
