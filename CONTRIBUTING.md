# Contributing

Contributions should stay scoped to the standalone package under `standalone/linkedin-apply-assistant/`.

## Local Setup

```powershell
python -m pip install -e ".[dev]"
python scripts\quality.py
```

The current repository root smoke command is:

```powershell
node test-all.mjs --quick
```

## Contribution Rules

- Keep examples synthetic.
- Do not commit credentials, cookies, browser profiles, screenshots, CVs, private documents, generated local reports, full private URLs, or live job history.
- Preserve the no-submit default.
- Do not add broad approvals, background sending, hidden submission, or unattended apply behavior.
- Do not make claims that the package is legal advice, platform compliant, audit certified, or guaranteed to succeed.
- Keep public docs English-only until localization is explicitly planned.

## Community and Reporting

- Support and setup help start in [SUPPORT.md](SUPPORT.md).
- Governance decisions follow [GOVERNANCE.md](GOVERNANCE.md).
- Conduct expectations and private conduct reporting are in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Vulnerability reporting stays in [SECURITY.md](SECURITY.md); do not post exploit details publicly.
- Public reports should use [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/).
- Pull requests should follow [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

Issue and pull request templates are the expected public contribution path. Keep
private runtime data out of issues and pull requests.

## Tests and Quality

Run the package quality gate before proposing changes:

```powershell
python scripts\quality.py
```

Focused package tests:

```powershell
python -m pytest tests -q
```

Live LinkedIn or Scrapling tests are opt-in only and must stay out of default CI. Use `CAREER_OPS_RUN_LIVE_TESTS=1` only when you intentionally run live tests in a controlled local environment.

## Pull Requests

Include:

- what changed
- why it is safe for the no-submit boundary
- commands run
- any residual release risk

If you add docs or examples, update docs smoke, privacy scan, or release-readiness tests as needed.
