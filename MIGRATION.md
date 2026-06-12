# Migration and Provenance

LinkedIn-apply-assistant is a standalone extraction of local LinkedIn job-search and application-assistance code. It keeps the package surfaces needed for search-only, visible-browser assistive filling, prepare-only apply audits, dry runs, and local report review.

## What Moved

The standalone package contains:

- Python package metadata and console entry point
- importable automation modules
- package-local config and Q&A examples
- synthetic input and report examples
- package-local tests and quality gate
- public docs, safety, legal, contribution, security, changelog, license, and notice files

## What Stayed Behind

The standalone package intentionally excludes the broader Career-Ops ecosystem:

- evaluation modes and scoring prompts
- application tracker workflows
- portal scanning and batch processing scripts
- dashboard and updater logic
- CV generation
- generated reports and runtime output
- root agent workflow artifacts
- private user-layer data

Do not copy those root surfaces into the standalone package as required public setup.

## Runtime and Private Data Boundary

Keep these local and ignored:

- real config files
- real Q&A banks
- local workspace data
- visible-browser profiles
- generated outputs
- local reports
- private documents

Use the example files only as shape references. Do not publish browser state, credentials, private documents, full private URLs, screenshots, generated local reports, or live job history.

## Maintainer Notes

Career-Ops may appear in this package only for neutral attribution, provenance, migration, or notice context. Product identity belongs to LinkedIn-apply-assistant.

Scrapling is documented as a normal dependency and notice item. Do not describe it as a stealth, bypass, anti-detection, or product identity claim.

