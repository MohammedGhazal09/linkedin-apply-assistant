from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"
PACKAGE_DIR = SRC_DIR / "linkedin_apply_assistant"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def test_required_package_modules_import() -> None:
    import linkedin_apply_assistant.apply_reports
    import linkedin_apply_assistant.ats_handlers
    import linkedin_apply_assistant.browser_sessions
    import linkedin_apply_assistant.contracts
    import linkedin_apply_assistant.form_engine
    import linkedin_apply_assistant.linkedin_layer
    import linkedin_apply_assistant.page_actions
    import linkedin_apply_assistant.page_selectors
    import linkedin_apply_assistant.qa_bank
    import linkedin_apply_assistant.redaction
    import linkedin_apply_assistant.safety
    import linkedin_apply_assistant.workflows

    assert (
        linkedin_apply_assistant.form_engine.detect_ats("https://boards.greenhouse.io/example")
        == "greenhouse"
    )
    assert (
        linkedin_apply_assistant.browser_sessions.page_auth_status(
            type("Page", (), {"url": "https://notlinkedin.com/login"})()
        )
        == "ready"
    )


def test_all_module_imports_have_no_cwd_side_effects(tmp_path: Path) -> None:
    modules = (
        "linkedin_apply_assistant",
        "linkedin_apply_assistant.apply_reports",
        "linkedin_apply_assistant.ats_handlers",
        "linkedin_apply_assistant.browser_sessions",
        "linkedin_apply_assistant.contracts",
        "linkedin_apply_assistant.form_engine",
        "linkedin_apply_assistant.linkedin_layer",
        "linkedin_apply_assistant.page_actions",
        "linkedin_apply_assistant.page_selectors",
        "linkedin_apply_assistant.qa_bank",
        "linkedin_apply_assistant.redaction",
        "linkedin_apply_assistant.safety",
        "linkedin_apply_assistant.workflows",
    )
    code = "; ".join(f"import {module}" for module in modules) + "; print('ok')"

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"

    forbidden_paths = (
        tmp_path / ("linkedin" + "_user_data"),
        tmp_path / "output",
        tmp_path / "reports",
        tmp_path / "config" / ("profile" + ".yml"),
        tmp_path / (".scrapling" + "_browser_profile"),
        tmp_path / ("cv" + ".md"),
        tmp_path / "output" / "cvs",
        tmp_path / "browser-profile",
        tmp_path / "data",
    )
    for path in forbidden_paths:
        assert not path.exists(), f"unexpected import side effect: {path}"


def test_package_source_has_no_bare_root_imports() -> None:
    blocked = [
        "from " + name
        for name in (
            "form_engine",
            "qa_bank",
            "ats_handlers",
            "linkedin_layer",
            "apply_reports",
        )
    ]
    blocked += [
        "import " + name
        for name in (
            "form_engine",
            "qa_bank",
            "ats_handlers",
            "linkedin_layer",
            "apply_reports",
        )
    ]
    for source_path in PACKAGE_DIR.glob("*.py"):
        text = source_path.read_text(encoding="utf-8")
        for term in blocked:
            assert term not in text, f"{source_path} contains bare root import {term!r}"


def test_linkedin_search_url_sanitizer_rejects_lookalike_hosts() -> None:
    from linkedin_apply_assistant.linkedin_layer import sanitize_linkedin_search_url

    lookalike_url = "https://notlinkedin.com/jobs/search/?currentJobId=123&start=25&x=1"
    linkedin_url = "https://www.linkedin.com/jobs/search/?currentJobId=123&start=25&x=1"

    assert sanitize_linkedin_search_url(lookalike_url) == lookalike_url
    assert sanitize_linkedin_search_url(linkedin_url) == (
        "https://www.linkedin.com/jobs/search/?x=1"
    )
