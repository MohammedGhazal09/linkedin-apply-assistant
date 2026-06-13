# Install and Configuration

This package runs locally. You install the Python package, choose a local workspace, and keep personal runtime files out of version control.

This file is the canonical install matrix. The README keeps only a short quick start.

Current package metadata version: `0.1.0`.

Registry package channels are not live yet. The future package-channel decision,
approval gates, and no-backfill policy are documented in the
[registry publication strategy](registry-publication-strategy.md).

## Prerequisites

- Python 3.11 or newer.
- A shell such as PowerShell, Bash, zsh, or another POSIX-like shell.
- Node.js/npm only if you are validating the optional npm launcher package.
- Playwright Chromium only for visible-browser workflows.

Browser-free commands such as `dry-run` and `report` do not need a Playwright browser install. Commands that open a visible browser, such as `search`, `assist`, and browser-dependent `apply` preparation, need Chromium:

```powershell
python -m playwright install chromium
```

## Current Source Checkout

Run these commands from the package root, not from a broader parent repository root.

Install the package for local development:

```powershell
python -m pip install -e ".[dev]"
```

Check the console command:

```powershell
linkedin-apply-assistant --help
linkedin-apply-assistant config check
```

After installation, use the [command reference](commands.md) for first-run diagnostics, public command examples, output paths, reports, and browser-profile guidance.

If you are working directly from source and need a module fallback, set `PYTHONPATH` to the local `src` directory.

PowerShell:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
python -m linkedin_apply_assistant.cli --help
```

Bash/macOS/Linux:

```bash
PYTHONPATH="$(pwd)/src" python -m linkedin_apply_assistant.cli --help
```

## Public Source Download

The canonical public source repository is:

```text
https://github.com/MohammedGhazal09/linkedin-apply-assistant
```

Git clone:

```bash
git clone https://github.com/MohammedGhazal09/linkedin-apply-assistant.git
cd linkedin-apply-assistant
python -m pip install -e ".[dev]"
linkedin-apply-assistant --help
```

ZIP/tarball archive shape:

1. Download the ZIP/tarball archive from the public repository source archive links.
2. Extract it.
3. Open a shell in the extracted package root.
4. Install and verify:

```bash
python -m pip install -e ".[dev]"
linkedin-apply-assistant --help
```

## Python Install Paths

For a local package root checkout:

```powershell
python -m pip install .
linkedin-apply-assistant --help
```

For editable development with test and release tooling:

```powershell
python -m pip install -e ".[dev]"
linkedin-apply-assistant --help
```

For an isolated application install with pipx from a local package root:

```powershell
pipx install .
linkedin-apply-assistant --help
```

After a later approved registry release, the future pipx command shape will use the package name:

```powershell
pipx install linkedin-apply-assistant
```

Until that release exists, use the local package-root commands above.

## npm Launcher Path

The package-local npm path is a thin launcher for users who want an npm-installed command. It delegates to the Python CLI and does not install Python dependencies for you.

From the package root, test the launcher locally after making the Python package importable.

PowerShell:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
node .\bin\linkedin-apply-assistant.mjs --help
```

Bash/macOS/Linux:

```bash
PYTHONPATH="$(pwd)/src" node ./bin/linkedin-apply-assistant.mjs --help
```

Local package-shape validation uses npm packaging dry runs rather than registry publication:

```powershell
npm pack --dry-run --json
```

After a later approved npm registry release, the future command shape will be:

```powershell
npm install -g linkedin-apply-assistant
linkedin-apply-assistant --help
```

Until that release exists, install the Python package from source first.

## Browser-Free Commands

`dry-run` validates local input without opening a browser:

```powershell
linkedin-apply-assistant dry-run --input examples\dry_run_input.example.json
```

`report` reads a local report JSON file and prints a summary without opening a browser:

```powershell
linkedin-apply-assistant report examples\reports\apply-audit.example.json
```

## Visible-Browser Workflows

Visible-browser workflows are user-controlled and no-submit by default. Use the Playwright Chromium prerequisite command above before opening them.

Then review each command's help:

```powershell
linkedin-apply-assistant config check
linkedin-apply-assistant search --help
linkedin-apply-assistant assist --help
linkedin-apply-assistant apply --help
```

`search` collects candidate job context and writes local reports. `assist` opens a visible-browser fill-only session. `apply` prepares approval-gated audit output; browser submission remains disabled today.

## Workspace

Use `--workspace` to point the assistant at a local directory for config, data, visible-browser profile, outputs, and reports:

```powershell
linkedin-apply-assistant --workspace .\local-workspace dry-run --input examples\dry_run_input.example.json
```

The package `.gitignore` excludes local runtime directories such as `data/`, `output/`, `reports/`, `browser-profile/`, and local config files. Keep real answers and browser state local.

## Config

Start from [../configs/config.example.yml](../configs/config.example.yml). Copy it to your own ignored workspace before adding real local paths.

Use `--config` to choose the file:

```powershell
linkedin-apply-assistant --config .\local-workspace\config.yml dry-run --input examples\dry_run_input.example.json
```

Do not put credentials in the package config. Browser login state belongs in your local visible-browser profile, and the profile directory should stay ignored.

## Q&A Bank

Start from [../configs/qa_bank.example.yml](../configs/qa_bank.example.yml). The Q&A bank should contain truthful, reusable answers only. Unknown required questions should stop the workflow until the user supplies an answer.

Use `--qa-bank` to choose a local file:

```powershell
linkedin-apply-assistant --qa-bank .\local-workspace\qa_bank.yml dry-run --input examples\dry_run_input.example.json
```

## Output Directory

Use `--output-dir` when you want command output somewhere specific:

```powershell
linkedin-apply-assistant --output-dir .\local-workspace\outputs dry-run --input examples\dry_run_input.example.json
```

Generated output is local audit material. Do not publish it unless you have reviewed and sanitized it.
