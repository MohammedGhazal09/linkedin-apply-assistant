# LinkedIn-apply-assistant

LinkedIn-apply-assistant is an experimental local browser automation assistant for LinkedIn job workflows. It helps with search, visible-browser form filling, prepare-only apply audits, dry-run validation, and local report review while you stay in control of every browser session.

The package is local-first. It does not require credentials in config, copied browser profiles, private documents, or generated reports to import, inspect, or run its deterministic tests.

Current package metadata version: `0.1.0`.

## Safety Boundary

- Browser workflows are user-visible and user-controlled.
- Public workflows are no-submit by default.
- `apply` currently prepares local audit output and keeps browser submission disabled.
- `--confirm-submit` is a guarded future option; every submission would still require explicit per-submission confirmation and Phase 16 safety guardrails.
- Do not use the package for mass applications, unattended apply sessions, CAPTCHA or MFA bypass, fake answers, unrelated personal-data scraping, or continued automation after platform throttling.

Read [SAFETY.md](SAFETY.md) before using visible-browser workflows. Read [LEGAL.md](LEGAL.md) for platform responsibility, acceptable-use, and no-legal-advice / no-compliance-certification posture.

## Community and Support

- Support and setup routing: [SUPPORT.md](SUPPORT.md)
- Contributions: [CONTRIBUTING.md](CONTRIBUTING.md), [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/), and [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)
- Conduct and governance: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [GOVERNANCE.md](GOVERNANCE.md)
- Vulnerability reporting: [SECURITY.md](SECURITY.md)

## Install

From the package directory:

```powershell
python -m pip install -e ".[dev]"
linkedin-apply-assistant --help
```

For Bash/macOS/Linux:

```bash
python -m pip install -e ".[dev]"
linkedin-apply-assistant --help
```

For editable local development, this module fallback is available from the package root:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
python -m linkedin_apply_assistant.cli --help
```

Use Python 3.11 or newer. Install Playwright Chromium before visible-browser workflows such as `search`, `assist`, or browser-dependent `apply` preparation. Browser-free `dry-run` and `report` do not require Chromium.

The package also includes a local npm launcher shape for package dry-run validation. It delegates to the Python CLI and still requires the Python package to be installed or importable.

Source checkout is available at <https://github.com/MohammedGhazal09/linkedin-apply-assistant>. See [docs/install-and-configuration.md](docs/install-and-configuration.md) for the full source, Python, npm launcher, and Playwright install matrix. This package is still local-first; npm and PyPI registry releases remain pending until a later approved publish phase.

## Quick Start

1. Copy the example files you need into your own local workspace, then keep the real files ignored by version control:
   - [configs/config.example.yml](configs/config.example.yml)
   - [configs/qa_bank.example.yml](configs/qa_bank.example.yml)
   - [examples/dry_run_input.example.json](examples/dry_run_input.example.json)
2. Run a browser-free dry run:

   ```powershell
   linkedin-apply-assistant dry-run --input examples\dry_run_input.example.json
   ```

3. Review command help before running browser workflows:

   ```powershell
   linkedin-apply-assistant config check
   linkedin-apply-assistant search --help
   linkedin-apply-assistant assist --help
   linkedin-apply-assistant apply --help
   ```

4. Run the package quality gate before publishing or contributing:

   ```powershell
   python scripts\quality.py
   ```

The current root smoke command remains:

```powershell
node test-all.mjs --quick
```

## Public Commands

All commands accept these shared flags where relevant: `--workspace`, `--config`, `--qa-bank`, `--browser-profile`, `--output-dir`, and `--verbose`.

| Command | Purpose | Key flags |
|---|---|---|
| `config check` | Inspect first-run paths and setup gaps without creating files. | `--workspace`, `--config`, `--qa-bank`, `--browser-profile`, `--output-dir` |
| `search` | Collect candidate job context and write local reports without submitting applications. | `--query`, `--location`, `--limit`, `--search-url` |
| `assist` | Open a visible-browser fill-only session where the user drives the workflow. | `--start-url`, `--mode`, `--max-cycles` |
| `apply` | Prepare approval-gated application audit output. Browser submission remains disabled today. | `--input`, `--limit`, `--confirm-submit` |
| `dry-run` | Validate local job input without browser or network submission. | `--input` |
| `report` | Read a local JSON report and print a concise summary. | `report_json` |

## Documentation Map

User workflow docs:

- [Install and configuration](docs/install-and-configuration.md)
- [Terminal command reference](docs/commands.md)
- [Visible browser session setup](docs/browser-session.md)
- [Search-only workflow](docs/search.md)
- [Assistive fill-only workflow](docs/assist.md)
- [Prepare-only apply workflow](docs/apply.md)
- [Report review](docs/reports.md)
- [Troubleshooting](docs/troubleshooting.md)

Release and maintainer docs:

- [SAFETY.md](SAFETY.md)
- [LEGAL.md](LEGAL.md)
- [LICENSE](LICENSE)
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- [MIGRATION.md](MIGRATION.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)
- [GOVERNANCE.md](GOVERNANCE.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/)
- [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)
- [CHANGELOG.md](CHANGELOG.md)
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

## Examples

- Config: [configs/config.example.yml](configs/config.example.yml)
- Q&A bank: [configs/qa_bank.example.yml](configs/qa_bank.example.yml)
- Dry-run input: [examples/dry_run_input.example.json](examples/dry_run_input.example.json)
- Synthetic reports: [examples/reports/search-report.example.json](examples/reports/search-report.example.json), [examples/reports/apply-audit.example.json](examples/reports/apply-audit.example.json)

All public examples are synthetic. Do not publish credentials, cookies, browser state, screenshots, private documents, full private URLs, generated local reports, or live job history.
