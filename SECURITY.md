# Security Policy

## Reporting Vulnerabilities

Use GitHub private vulnerability reporting for the standalone project when available.

If private reporting is not configured yet, open a maintainer-private channel before sharing exploit details publicly. A standalone security contact can be added here when the public repository is configured.

Do not use upstream personal contacts as the default standalone package security contact.

## Reporting Routes

- Usage and setup support belongs in [SUPPORT.md](SUPPORT.md).
- Public safety/compliance concerns can use [.github/ISSUE_TEMPLATE/safety_compliance.yml](.github/ISSUE_TEMPLATE/safety_compliance.yml) only without exploit details.
- Conduct reports belong in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and should use private reporting.
- Vulnerability details stay in this security policy and should not be posted publicly.

## What to Report

Report issues such as:

- credential or token exposure
- browser profile leakage
- report redaction failures
- unsafe submit behavior
- dependency vulnerabilities
- documentation that encourages unsafe platform behavior

## Local Secret and Browser Profile Safety

Keep local config, Q&A banks, visible-browser profiles, outputs, reports, and private documents out of version control. The package `.gitignore` contains the expected local runtime patterns.

Never attach browser profiles, cookies, credentials, screenshots, private documents, generated local reports, or full private URLs to public issues.

## Supported Versions

The initial standalone package version is `0.1.0`. Security guidance applies to the current unreleased and `0.1.0` package-local surfaces.
