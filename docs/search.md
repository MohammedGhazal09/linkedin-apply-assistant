# Search-Only Workflow

`search` collects candidate job context and writes local report output without submitting applications.

## Basic Search

```powershell
linkedin-apply-assistant search --query "applied ai engineer" --location "Remote" --limit 10
```

Use `--search-url` when you already have a LinkedIn jobs search URL:

```powershell
linkedin-apply-assistant search --search-url "https://www.linkedin.com/jobs/search/" --limit 5
```

## Shared Options

`search` accepts the shared package flags:

- `--workspace`
- `--config`
- `--qa-bank`
- `--browser-profile`
- `--output-dir`
- `--verbose`

Example:

```powershell
linkedin-apply-assistant --workspace .\local-workspace search --query "automation engineer" --location "Remote" --limit 5 --verbose
```

## Output

Search output is local audit material. Review it before sharing. Do not publish full private URLs, browser state, generated local reports, or live job history.

For report review, see [reports.md](reports.md).

