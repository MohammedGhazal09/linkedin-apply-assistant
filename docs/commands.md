# Command Reference

Use this page after installation to choose the right terminal command, inspect first-run paths, and understand where local output is written. The full install matrix remains in [Install and configuration](install-and-configuration.md).

## First-Run Checklist

1. Install the package from the current source/Python path documented in [Install and configuration](install-and-configuration.md).
2. Run the read-only diagnostic:

   ```powershell
   linkedin-apply-assistant config check
   ```

   `linkedin-apply-assistant config` is accepted as the same read-only
   diagnostic shortcut.

3. Copy example files into your own ignored workspace when you need them:
   - `configs/config.example.yml` for profile, documents, and path choices.
   - `configs/qa_bank.example.yml` for truthful reusable answers.
4. Install browser support before visible-browser workflows:

   ```powershell
   python -m playwright install chromium
   ```

5. Keep the safety boundary visible: public workflows are no-submit by default, `assist` is fill-only, and browser submission remains disabled in `apply`.

## Runtime Paths

`linkedin-apply-assistant config check` resolves these path categories without creating files or directories:

| Path category | Purpose |
|---|---|
| Config file | Optional YAML config selected by `--config` or the workspace default. |
| Q&A bank | Optional YAML answers selected by `--qa-bank` or the workspace default. |
| Browser profile | Local visible-browser profile directory used by browser workflows. |
| Output directory | Local command output directory. |
| Reports directory | Local JSON report directory under the output directory. |
| Data directory | Local assistant data such as pending questions. |
| Cache directory | Local cache data for workflows that need it. |

Use `--workspace` to keep those paths under one local directory:

```powershell
linkedin-apply-assistant --workspace .\local-workspace config check
```

Bash/macOS/Linux:

```bash
linkedin-apply-assistant --workspace ./local-workspace config check
```

## config check

Run diagnostics before browser workflows or after changing path flags:

```powershell
linkedin-apply-assistant config check
```

Shortcut:

```powershell
linkedin-apply-assistant config
```

Expected output:

- `ok`, `missing`, or `warning` for each path category.
- The resolved config file, Q&A bank, browser profile, output directory, reports directory, data directory, and cache directory.
- Setup guidance for missing config and missing Q&A bank.

This command is read-only. It does not create config files, Q&A bank files, browser profiles, output directories, reports directories, data directories, or cache directories.

Try: linkedin-apply-assistant config check

## search

`search` collects candidate job context and writes local reports without submitting applications.

```powershell
linkedin-apply-assistant search --query "python" --location "Remote" --limit 5
```

Use an existing LinkedIn search URL when you already have one:

```powershell
linkedin-apply-assistant search --search-url "https://www.linkedin.com/jobs/search/" --limit 10 --verbose
```

Notes:

- Visible browser search needs Playwright Chromium: `python -m playwright install chromium`.
- `--limit 0` remains browser-free and can write an empty search report.
- Reports are written under the resolved reports directory.
- Public workflows are no-submit by default.

## assist

`assist` opens a visible-browser session where you drive the browser and the assistant fills detected forms. It is fill-only.

```powershell
linkedin-apply-assistant assist --mode on-demand
```

Use an explicit workspace and browser profile when you want all local state grouped:

```powershell
linkedin-apply-assistant assist --workspace .\local-workspace --browser-profile .\local-workspace\browser-profile --verbose
```

Notes:

- Install browser support first: `python -m playwright install chromium`.
- Use a truthful Q&A bank based on `configs/qa_bank.example.yml`.
- Missing answers should pause filling or be captured as pending questions for review.
- Reports are written under the resolved reports directory.
- Browser submission remains disabled.

## apply

`apply` prepares local audit output. Browser submission remains disabled in this package boundary.

```powershell
linkedin-apply-assistant apply --input candidates.json --limit 3
```

Use verbose mode to see resolved report paths:

```powershell
linkedin-apply-assistant apply --workspace .\local-workspace --input candidates.json --verbose
```

Notes:

- Current behavior is prepare-only.
- `--confirm-submit` is recorded as a guarded future signal, but browser submission remains disabled.
- Reports are written under the resolved reports directory.
- Do not use the package for mass applications or unattended apply sessions.

## dry-run

`dry-run` validates local job JSON input. It is browser-free, does not require Playwright, does not require config, and does not require a browser profile.

```powershell
linkedin-apply-assistant dry-run --input examples\dry_run_input.example.json
```

Bash/macOS/Linux:

```bash
linkedin-apply-assistant dry-run --input examples/dry_run_input.example.json
```

Use this command to check JSON shape before browser workflows.

## report

`report` reads an existing local report JSON file and prints a concise summary. It is browser-free, does not require Playwright, does not require config, and does not require a browser profile.

```powershell
linkedin-apply-assistant report examples\reports\apply-audit.example.json
```

Bash/macOS/Linux:

```bash
linkedin-apply-assistant report examples/reports/apply-audit.example.json
```

Use this command for local report review without opening a browser.

## Troubleshooting Pointers

| Symptom | Next step |
|---|---|
| Missing config | Run `linkedin-apply-assistant config check`, then copy and edit `configs/config.example.yml` if you need config. |
| Missing Q&A bank | Copy `configs/qa_bank.example.yml`, answer truthfully, and pass it with `--qa-bank` or a workspace default. |
| Invalid JSON input | Re-run `dry-run` after checking the `--input` path and JSON format. |
| Missing Playwright or Chromium | Run `python -m playwright install chromium`. |
| Browser profile issue | Run `config check`, inspect the browser profile path, or choose another profile with `--browser-profile <path>`. |
| Unsure which command to use | Start with `linkedin-apply-assistant --help` and `linkedin-apply-assistant config check`. |

More details are in [Troubleshooting](troubleshooting.md).
