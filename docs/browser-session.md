# Visible Browser Session Setup

Browser workflows are local and user-visible. You drive or review the browser session; the package does not run hidden unattended apply workflows.

## Browser Profile

Use `--browser-profile` to choose a local profile directory:

```powershell
linkedin-apply-assistant --browser-profile .\local-workspace\browser-profile assist --mode on-demand
```

The profile can contain cookies, sessions, and local form state. Keep it ignored, local, and under your control. Do not copy it into examples, issues, fixtures, or reports.

## Login Flow

Open a visible browser session and log in yourself when the platform asks for it. If a checkpoint, rate limit, MFA prompt, or other platform risk signal appears, stop and resolve it manually.

The assistant must not bypass CAPTCHA, MFA, checkpoints, platform throttling, or employer application rules.

## Start URL

Use `assist --start-url` when you want the visible browser to open a specific starting page:

```powershell
linkedin-apply-assistant assist --start-url "https://www.linkedin.com/jobs/" --mode on-demand
```

Only use URLs you are comfortable opening in your own browser session. Do not publish full private application URLs in docs or examples.

## Session Modes

`assist` supports:

- `--mode on-demand`: inspect/fill only when requested by the user workflow.
- `--mode auto-watch`: watch for fillable surfaces and fill once per detected surface.

Example:

```powershell
linkedin-apply-assistant assist --mode auto-watch --max-cycles 3
```

Both modes remain fill-only boundaries. They do not submit applications.

