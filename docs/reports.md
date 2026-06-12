# Report Review

`report` reads a local JSON report and prints a concise summary for review.

## Review a Report

```powershell
linkedin-apply-assistant report examples\reports\search-report.example.json
```

Synthetic examples:

- [../examples/reports/search-report.example.json](../examples/reports/search-report.example.json)
- [../examples/reports/apply-audit.example.json](../examples/reports/apply-audit.example.json)

## Report Boundary

Reports are local audit material. They can contain company names, role names, status counts, blockers, and decisions. They should not contain credentials, cookies, tokens, raw browser state, raw HTML, screenshots, full private URLs, private documents, or generated local reports copied from a real run.

Use examples to understand shape only. Replace or redact sensitive data before sharing any report outside your machine.

## Related Commands

Generate browser-free dry-run output:

```powershell
linkedin-apply-assistant dry-run --input examples\dry_run_input.example.json
```

Prepare local apply audit output without browser submission:

```powershell
linkedin-apply-assistant apply --input examples\dry_run_input.example.json --limit 1
```

