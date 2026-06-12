# Safety and Acceptable Use

LinkedIn-apply-assistant is a local, user-controlled package. It is designed for search, review, and assistive form filling while the user drives a visible browser session.

## Operating Boundary

- Public workflows are no-submit by default.
- Apply preparation can produce an audit report, but browser submission remains disabled.
- Any future submit-capable release must require per-application interactive confirmation immediately before a specific application is sent.
- Broad approvals, background sending, and unattended modes are outside the package boundary.

## Forbidden Uses

Do not use this package for:

- mass applications or spam-like recruiting workflows
- unattended apply sessions
- CAPTCHA or MFA bypass
- fake answers or guessed application responses
- unrelated personal-data scraping
- continuing automation after platform throttling, rate limits, checkpoints, or similar risk signals

Unknown required questions must stop completion until the user supplies a truthful answer.

## Local Privacy Boundary

Visible browser profiles can contain cookies, sessions, and local form data. Keep the browser profile directory local, ignored by version control, and under your control.

Reports and pending-question logs are intended for local audit and follow-up. They should keep useful metadata such as company, role, ATS, domain, status, counts, blockers, and policy decisions while excluding credentials, cookies, tokens, raw browser state, screenshots, full documents, private profile dumps, and full application URLs by default.

## Platform and Legal Responsibility

You are responsible for following platform terms, employer application rules, and local law. This document is not legal advice and is not a compliance certification for GDPR, CCPA, LinkedIn terms, SOC 2, or any other legal, platform, or audit framework.
