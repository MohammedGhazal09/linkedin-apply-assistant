from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = PACKAGE_ROOT / ".github" / "workflows"
QUALITY_WORKFLOW = WORKFLOWS_DIR / "quality.yml"
SECURITY_WORKFLOW = WORKFLOWS_DIR / "security.yml"
DEPENDABOT = PACKAGE_ROOT / ".github" / "dependabot.yml"


class ActionsYamlLoader(yaml.SafeLoader):
    """PyYAML loader that keeps GitHub Actions `on` as a string key."""


ActionsYamlLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


FORBIDDEN_WORKFLOW_PATTERNS = (
    r"\bnpm\s+publish\b",
    r"\bpnpm\s+publish\b",
    r"\byarn\s+npm\s+publish\b",
    r"\btwine\s+upload\b",
    r"\bpython\s+-m\s+twine\s+upload\b",
    r"\bgh\s+release\s+(create|edit|delete|upload)\b",
    r"\bgit\s+tag\b",
    r"\bgit\s+push\s+--tags\b",
    r"\bgit\s+push\s+origin\s+--tags\b",
    r"\bgit\s+push\s+origin\s+refs/tags\b",
    r"\bnpm\s+(login|adduser)\b",
    r"\bpypi\.org\b",
    r"\btest\.pypi\.org\b",
    r"trusted[- ]publisher",
    r"rulesets?",
    r"branches/protection",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=ActionsYamlLoader)
    assert isinstance(loaded, dict), path
    return loaded


def _workflow_paths() -> tuple[Path, ...]:
    return tuple(sorted(WORKFLOWS_DIR.glob("*.yml"))) + tuple(sorted(WORKFLOWS_DIR.glob("*.yaml")))


def _events(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("on")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {str(item): None for item in raw}
    raise AssertionError(f"workflow has invalid on block: {raw!r}")


def _assert_main_push(events: dict[str, Any]) -> None:
    push = events.get("push")
    assert isinstance(push, dict)
    assert push.get("branches") == ["main"]


def _assert_concurrency(config: dict[str, Any]) -> None:
    concurrency = config.get("concurrency")
    assert isinstance(concurrency, dict)
    assert "${{ github.workflow }}" in str(concurrency.get("group"))
    assert "${{ github.ref }}" in str(concurrency.get("group"))
    assert str(concurrency.get("cancel-in-progress")).lower() == "true"


def _all_steps(config: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for job in config.get("jobs", {}).values():
        if isinstance(job, dict):
            for step in job.get("steps", []):
                if isinstance(step, dict):
                    steps.append(step)
    return steps


def _workflow_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in _workflow_paths()).lower()


def test_phase28_workflows_exist_with_stable_names() -> None:
    assert QUALITY_WORKFLOW.is_file()
    assert SECURITY_WORKFLOW.is_file()
    assert {path.name for path in _workflow_paths()} == {"quality.yml", "security.yml"}

    assert _load_yaml(QUALITY_WORKFLOW)["name"] == "Quality"
    assert _load_yaml(SECURITY_WORKFLOW)["name"] == "Security"


def test_workflows_use_expected_triggers_and_concurrency() -> None:
    quality = _load_yaml(QUALITY_WORKFLOW)
    security = _load_yaml(SECURITY_WORKFLOW)

    quality_events = _events(quality)
    security_events = _events(security)

    for event_name in ("pull_request", "push", "workflow_dispatch"):
        assert event_name in quality_events
        assert event_name in security_events

    assert "schedule" not in quality_events
    assert "schedule" in security_events
    assert isinstance(security_events["schedule"], list)
    _assert_main_push(quality_events)
    _assert_main_push(security_events)
    _assert_concurrency(quality)
    _assert_concurrency(security)


def test_workflows_keep_permissions_minimal() -> None:
    for path in _workflow_paths():
        config = _load_yaml(path)
        assert config.get("permissions") == {"contents": "read"}
        jobs = config.get("jobs")
        assert isinstance(jobs, dict)

        for job_id, job in jobs.items():
            assert isinstance(job, dict)
            permissions = job.get("permissions", {})
            if permissions == {}:
                continue
            assert isinstance(permissions, dict)
            for permission, value in permissions.items():
                if value != "write":
                    continue
                assert path.name == "security.yml"
                assert job_id == "codeql"
                assert permission == "security-events"


def test_workflows_do_not_publish_or_mutate_release_state() -> None:
    text = _workflow_text()
    for pattern in FORBIDDEN_WORKFLOW_PATTERNS:
        assert re.search(pattern, text) is None, pattern

    for forbidden_permission in ("packages: write", "id-token: write", "attestations: write"):
        assert forbidden_permission not in text


def test_quality_workflow_runtime_and_release_smoke_contract() -> None:
    config = _load_yaml(QUALITY_WORKFLOW)
    jobs = config["jobs"]

    assert set(jobs) == {"quality", "release-smoke"}
    assert jobs["quality"]["name"] == "quality"
    assert jobs["release-smoke"]["name"] == "release-smoke"
    assert jobs["quality"]["runs-on"] == "ubuntu-latest"
    assert "os" not in jobs["quality"]["strategy"]["matrix"]
    assert jobs["quality"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12"]

    text = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    assert 'python -m pip install -e ".[dev]"' in text
    assert "python scripts/quality.py" in text
    assert "python scripts/release.py manifest --check" in text
    assert "python scripts/release.py verify" in text
    assert "npm pack --dry-run --json" in text
    assert "npm ci" not in text
    assert 'node-version: "24"' in text

    action_text = "\n".join(str(step.get("uses", "")) for step in _all_steps(config))
    assert re.search(r"actions/checkout@v6(?:\.|$)", action_text)
    assert re.search(r"actions/setup-python@v6(?:\.|$)", action_text)
    assert re.search(r"actions/setup-node@v6(?:\.|$)", action_text)


def test_security_workflow_configures_codeql_dependency_review_and_gitleaks() -> None:
    config = _load_yaml(SECURITY_WORKFLOW)
    jobs = config["jobs"]

    assert set(jobs) == {"codeql", "dependency-review", "secret-scan"}
    assert jobs["codeql"]["name"] == "codeql"
    assert jobs["dependency-review"]["name"] == "dependency-review"
    assert jobs["secret-scan"]["name"] == "secret-scan"
    assert jobs["codeql"]["strategy"]["matrix"]["language"] == ["python", "javascript"]

    text = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"github/codeql-action/init@v4(?:\.|$)", text)
    assert re.search(r"github/codeql-action/analyze@v4(?:\.|$)", text)
    assert "queries: security-extended" in text
    assert re.search(r"actions/dependency-review-action@v5(?:\.|$)", text)
    assert "fail-on-severity: high" in text
    assert "github.event_name == 'pull_request'" in text
    assert re.search(r"gitleaks/gitleaks-action@v3(?:\.|$)", text)
    assert "fetch-depth: 0" in text

    gitleaks_steps = [
        step
        for step in jobs["secret-scan"]["steps"]
        if str(step.get("uses", "")).startswith("gitleaks/gitleaks-action@")
    ]
    assert len(gitleaks_steps) == 1
    assert gitleaks_steps[0]["env"] == {
        "GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "GITLEAKS_ENABLE_COMMENTS": "false",
    }


def test_dependabot_weekly_grouped_root_ecosystems_without_auto_merge() -> None:
    config = _load_yaml(DEPENDABOT)

    assert config["version"] == 2
    updates = config["updates"]
    ecosystems = {entry["package-ecosystem"]: entry for entry in updates}
    assert set(ecosystems) == {"github-actions", "npm", "pip"}

    for entry in ecosystems.values():
        assert entry["directory"] == "/"
        assert entry["schedule"]["interval"] == "weekly"
        assert entry["open-pull-requests-limit"] == 5
        assert entry["groups"]
        assert "labels" not in entry
        assert "assignees" not in entry

    text = DEPENDABOT.read_text(encoding="utf-8").lower()
    assert "auto-merge" not in text
    assert "automerge" not in text
