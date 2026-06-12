"""Named selector groups for page adapters."""

from __future__ import annotations


PROFILE_FIELD_SELECTORS: dict[str, dict[str, tuple[str, ...]]] = {
    "greenhouse": {
        "first_name": ("#first_name", 'input[name*="first_name" i]'),
        "last_name": ("#last_name", 'input[name*="last_name" i]'),
        "email": ('input[type="email"]', 'input[name*="email" i]'),
        "phone": ('input[type="tel"]', 'input[name*="phone" i]'),
        "linkedin": ('input[name*="linkedin" i]',),
        "portfolio": ('input[name*="website" i]', 'input[name*="portfolio" i]'),
    },
    "lever": {
        "full_name": ('input[name="name"]',),
        "email": ('input[name="email"]', 'input[type="email"]'),
        "phone": ('input[name="phone"]', 'input[type="tel"]'),
        "current_company": ('input[name="org"]',),
        "linkedin": ('input[name="urls[LinkedIn]"]',),
        "portfolio": ('input[name="urls[Portfolio]"]',),
        "github": ('input[name="urls[GitHub]"]',),
    },
    "ashby": {
        "full_name": ('input[name="_systemfield_name"]', 'input[id*="name" i]'),
        "email": ('input[name="_systemfield_email"]', 'input[type="email"]'),
        "phone": ('input[name="_systemfield_phone"]', 'input[type="tel"]'),
        "linkedin": ('input[name*="linkedin" i]', 'input[id*="linkedin" i]'),
        "portfolio": ('input[name*="website" i]', 'input[id*="portfolio" i]'),
    },
    "generic": {
        "email": ('input[type="email"]', 'input[name*="email" i]'),
        "phone": ('input[type="tel"]', 'input[name*="phone" i]'),
        "first_name": ('input[name*="first" i]',),
        "last_name": ('input[name*="last" i]',),
        "full_name": ('input[autocomplete="name"]', 'input[name*="name" i]'),
        "linkedin": ('input[name*="linkedin" i]',),
        "portfolio": ('input[name*="portfolio" i]', 'input[name*="website" i]'),
        "github": ('input[name*="github" i]',),
    },
    "linkedin_easy_apply": {
        "first_name": ('input[name*="first" i]',),
        "last_name": ('input[name*="last" i]',),
        "full_name": ('input[autocomplete="name"]',),
        "email": ('input[type="email"]',),
        "phone": ('input[type="tel"]',),
        "linkedin": ('input[name*="linkedin" i]',),
        "portfolio": ('input[name*="portfolio" i]', 'input[name*="website" i]'),
    },
}


DOCUMENT_SELECTORS: dict[str, tuple[str, ...]] = {
    "resume": (
        'input[type="file"][name*="resume" i]',
        'input[type="file"][id*="resume" i]',
        'input[type="file"][aria-label*="resume" i]',
        'input[type="file"][name*="cv" i]',
        'input[type="file"][id*="cv" i]',
    ),
    "cover_letter": (
        'input[type="file"][name*="cover" i]',
        'input[type="file"][id*="cover" i]',
        'input[type="file"][aria-label*="cover" i]',
    ),
}


QUESTION_SELECTORS: tuple[str, ...] = (
    "label",
    "[data-test-form-element]",
    "[data-qa-form-element]",
    ".form-question",
)


EASY_APPLY_ACTIONS: dict[str, tuple[str, ...]] = {
    "advance": ("Next", "Continue", "Review"),
    "final": ("final",),
}


__all__ = [
    "DOCUMENT_SELECTORS",
    "EASY_APPLY_ACTIONS",
    "PROFILE_FIELD_SELECTORS",
    "QUESTION_SELECTORS",
]
