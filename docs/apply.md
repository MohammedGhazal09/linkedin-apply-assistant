# Prepare-Only Apply Workflow

`apply` prepares local application audit output from candidate job input. Browser submission remains disabled in the current public package.

## Prepare From Input

Use synthetic or local candidate job input:

```powershell
linkedin-apply-assistant apply --input examples\dry_run_input.example.json --limit 1
```

The input file should not contain credentials, private documents, browser state, screenshots, full private URLs, or live job history.

## Guarded Future Option

The CLI exposes `--confirm-submit` as a guarded future option:

```powershell
linkedin-apply-assistant apply --input examples\dry_run_input.example.json --limit 1 --confirm-submit
```

Current browser submission remains disabled. Any future submit-capable release must still require explicit per-submission confirmation immediately before a specific application is sent, and must preserve the safety guardrails described in [../SAFETY.md](../SAFETY.md).

## Shared Options

`apply` accepts:

- `--workspace`
- `--config`
- `--qa-bank`
- `--browser-profile`
- `--output-dir`
- `--verbose`
- `--input`
- `--limit`
- `--confirm-submit`

Do not use `apply` for mass applications, unattended apply sessions, fake answers, CAPTCHA or MFA bypass, or continued automation after platform risk signals.

