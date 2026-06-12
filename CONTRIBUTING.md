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
- Do not commit credentials, cookies, browser state, screenshots, private documents, full private URLs, generated local reports, or live job history.
- Preserve the no-submit default.
- Do not add broad approvals, background sending, hidden submission, or unattended apply behavior.
- Do not make claims that the package is legal advice, platform compliant, audit certified, or guaranteed to succeed.
- Keep public docs English-only until localization is explicitly planned.

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
