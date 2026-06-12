from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
PACKAGE_JSON = PACKAGE_ROOT / "package.json"
INIT_PY = PACKAGE_ROOT / "src" / "linkedin_apply_assistant" / "__init__.py"
CHANGELOG = PACKAGE_ROOT / "CHANGELOG.md"
RELEASE_CHECKLIST = PACKAGE_ROOT / "RELEASE_CHECKLIST.md"
README = PACKAGE_ROOT / "README.md"
INSTALL_DOC = PACKAGE_ROOT / "docs" / "install-and-configuration.md"


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _package_json() -> dict[str, object]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _init_constant(name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']",
        INIT_PY.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, name
    return match.group(1)


def test_python_and_npm_package_identity_stays_synchronized() -> None:
    pyproject_project = _pyproject()["project"]
    package = _package_json()

    assert pyproject_project["name"] == "linkedin-apply-assistant"
    assert pyproject_project["version"] == "0.1.0"
    assert package["name"] == pyproject_project["name"]
    assert package["version"] == pyproject_project["version"]
    assert _init_constant("__version__") == pyproject_project["version"]
    assert _init_constant("APP_PACKAGE_NAME") == pyproject_project["name"]
    assert _init_constant("APP_IMPORT_NAME") == "linkedin_apply_assistant"
    assert _init_constant("APP_COMMAND_NAME") == "linkedin-apply-assistant"


def test_command_and_launcher_metadata_stays_synchronized() -> None:
    pyproject_project = _pyproject()["project"]
    package = _package_json()

    assert pyproject_project["scripts"] == {
        "linkedin-apply-assistant": "linkedin_apply_assistant.cli:main"
    }
    assert package["bin"] == {"linkedin-apply-assistant": "./bin/linkedin-apply-assistant.mjs"}
    assert (PACKAGE_ROOT / "bin" / "linkedin-apply-assistant.mjs").is_file()


def test_build_tool_is_declared_for_distribution_verification() -> None:
    optional_deps = _pyproject()["project"]["optional-dependencies"]
    dev_deps = optional_deps["dev"]

    assert any(dep.startswith("build>=") for dep in dev_deps)


def test_distribution_docs_and_release_surfaces_include_identity() -> None:
    docs = {
        "README.md": README.read_text(encoding="utf-8"),
        "docs/install-and-configuration.md": INSTALL_DOC.read_text(encoding="utf-8"),
        "CHANGELOG.md": CHANGELOG.read_text(encoding="utf-8"),
        "RELEASE_CHECKLIST.md": RELEASE_CHECKLIST.read_text(encoding="utf-8"),
    }

    for path, text in docs.items():
        assert "linkedin-apply-assistant" in text, path
        assert "0.1.0" in text, path

    assert "linkedin_apply_assistant" in docs["README.md"]
    assert "linkedin_apply_assistant" in docs["docs/install-and-configuration.md"]
    assert "python -m pip install ." in docs["docs/install-and-configuration.md"]
    assert 'python -m pip install -e ".[dev]"' in docs["docs/install-and-configuration.md"]
    assert (
        "python -m linkedin_apply_assistant.cli --help"
        in (docs["docs/install-and-configuration.md"])
    )


def test_future_registry_and_remote_wording_is_labeled() -> None:
    readme = README.read_text(encoding="utf-8").lower()
    install_doc = INSTALL_DOC.read_text(encoding="utf-8").lower()

    assert "does not claim a live public repository" in readme
    assert "future git clone shape" in install_doc
    assert "future zip/tarball archive shape" in install_doc
    assert "after a later approved npm registry release" in install_doc
    assert "until that release exists" in install_doc
    assert "git clone <future-public-repository-url>" in install_doc
    assert "git clone https://" not in install_doc


def test_package_json_omits_live_repository_metadata_until_public_repo_exists() -> None:
    package = _package_json()

    assert "repository" not in package
    assert "homepage" not in package
    assert "bugs" not in package
