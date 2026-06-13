# CI and Release Policy

This repository uses CI to make public project health visible without creating
tags, GitHub Releases, package uploads, registry tokens, attestations, or
repository-setting changes.

## Workflows

Two user-authored GitHub Actions workflows are expected on `main`:

- `Quality` at `.github/workflows/quality.yml`
- `Security` at `.github/workflows/security.yml`

Both workflows run on pull requests, pushes to `main`, and manual dispatch. Only
`Security` has a weekly scheduled scan. Both workflows use concurrency with
`cancel-in-progress` so stale branch runs do not consume runner capacity.

## Quality

The `Quality` workflow has two jobs:

- `quality` runs on Ubuntu with Python `3.11` and `3.12`.
- `release-smoke` runs once with Python `3.12` and Node.js `24`.

The workflow installs Python dependencies with:

```bash
python -m pip install -e ".[dev]"
```

It does not require `npm ci` because the package does not currently ship a
standalone lockfile. The release-smoke job validates the release manifest, runs
focused release-readiness tests, runs `python scripts/release.py verify`, and
checks npm launcher package shape with `npm pack --dry-run --json`.

The CI suite intentionally stays browser-free. It does not run live LinkedIn,
browser-profile, final-submit, or user-layer-file workflows.

## Security

The `Security` workflow has three jobs:

- `codeql` runs committed CodeQL advanced setup for Python and JavaScript only,
  with `security-extended` queries.
- `dependency-review` runs only on pull requests and fails on high or critical
  dependency risk through `fail-on-severity: high`.
- `secret-scan` runs Gitleaks against the checked-out repository history.

Workflow permissions default to `contents: read`. The only write permission is
`security-events: write`, and it is limited to the CodeQL job.
The Gitleaks step receives the default `GITHUB_TOKEN` only for action API access
and sets `GITLEAKS_ENABLE_COMMENTS=false`, so it does not need pull-request write
permissions.

Phase 28 deliberately does not add Bandit, Semgrep, or another extra SAST tool.
Dependabot covers GitHub Actions, npm, and pip at repository root `/` with
weekly grouped updates, open pull request limit `5`, and no auto-merge. Labels
and assignees are skipped unless maintainers add a label policy later.

## Release Automation Boundary

This project currently uses manual GitHub source releases. Phase 28 does not
enable Release Please, semantic-release, tag automation, changelog automation,
or any equivalent release writer.

Conventional Commits are recommended for maintainability, but CI does not
enforce commit-message format.

The workflows and Dependabot config are source-release metadata. They are kept
in `release-manifest.json` for source-checkout visibility, but workflow files
and `.github/dependabot.yml` are excluded from npm package contents unless a
future phase intentionally documents otherwise.

## Deferred Provenance Work

The following controls are feasible future work, not active behavior:

- SBOM generation, after a real artifact channel is selected.
- Artifact attestations, after the project intentionally grants
  `id-token: write` and `attestations: write`.
- Signing and immutable-release policy, after release assets or package
  channels exist.
- Trusted publisher setup or package-name reservation, in a dedicated registry
  publication phase.

The future registry channel order, trusted-publishing boundary, approval
templates, and rollback limits are documented in the
[registry publication strategy](registry-publication-strategy.md).

No Phase 28 workflow grants `packages: write`, `id-token: write`, or
`attestations: write`.

## No-Surprise Publish Boundary

Phase 28 automation must not:

- run `npm publish`
- run `twine upload`
- create, edit, delete, or upload a GitHub Release
- create or push tags
- reserve package names
- configure trusted publishers
- mutate branch rulesets, tag rulesets, required checks, or repository settings

Public sync and live workflow verification remain explicit maintainer actions.
