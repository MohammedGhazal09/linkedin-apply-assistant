# Assistive Fill-Only Workflow

`assist` opens a visible-browser workflow where the user drives the session and the assistant fills supported fields. It is a fill-only boundary.

## On-Demand Mode

Use on-demand mode when you want to control each fill attempt:

```powershell
linkedin-apply-assistant assist --mode on-demand --max-cycles 3
```

## Auto-Watch Mode

Use auto-watch when you want the assistant to inspect detected fillable surfaces:

```powershell
linkedin-apply-assistant assist --mode auto-watch --max-cycles 3
```

## Start Page

```powershell
linkedin-apply-assistant assist --start-url "https://www.linkedin.com/jobs/" --mode on-demand
```

## Boundaries

- You remain responsible for the browser session.
- Unknown required questions should stop until you provide a truthful answer.
- The assistant must not submit applications in this workflow.
- The assistant must not continue through CAPTCHA, MFA, checkpoints, platform throttling, or similar risk signals.

For browser profile safety, see [browser-session.md](browser-session.md).

