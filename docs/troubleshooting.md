# Troubleshooting

Start with the command help:

```powershell
linkedin-apply-assistant --help
linkedin-apply-assistant config check
linkedin-apply-assistant config check --help
linkedin-apply-assistant search --help
linkedin-apply-assistant assist --help
linkedin-apply-assistant apply --help
linkedin-apply-assistant dry-run --help
linkedin-apply-assistant report --help
```

For normal command examples, resolved output paths, reports, browser profile location, and first-run setup, read the [command reference](commands.md).

## Command Not Found

Install the package in editable mode:

```powershell
python -m pip install -e ".[dev]"
```

Or use the module fallback:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
python -m linkedin_apply_assistant.cli --help
```

## Browser Does Not Open

- Confirm Playwright is installed with the package dependencies.
- Install Chromium with `python -m playwright install chromium`.
- Run `linkedin-apply-assistant config check` to inspect the resolved browser profile path.
- Use `--browser-profile` with a local ignored directory.
- Avoid copying browser profile directories between machines or into public artifacts.

## Unknown Required Questions

Update your local Q&A bank from [../configs/qa_bank.example.yml](../configs/qa_bank.example.yml). Unknown required questions should pause the workflow until you can provide a truthful answer.

## Selector Drift

LinkedIn and ATS pages can change. If a visible-browser workflow stops detecting fields, reduce scope to `dry-run` or `report`, capture a sanitized description, and add or update tests before changing selectors.

## Quality Gate Failure

Run the package quality gate from the package root:

```powershell
python scripts\quality.py
```

The gate runs compile checks, package pytest, Ruff check, Ruff format check, dependency audit, docs smoke tests, privacy scans, and release-readiness checks.
