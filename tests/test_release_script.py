from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPT = PACKAGE_ROOT / "scripts" / "release.py"


def _load_release_module():
    spec = importlib.util.spec_from_file_location("release_script_for_tests", RELEASE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_clean_removes_only_package_scoped_generated_artifacts(tmp_path: Path) -> None:
    release = _load_release_module()
    generated_dirs = (
        tmp_path / "src" / "pkg" / "__pycache__",
        tmp_path / ".pytest_cache",
        tmp_path / ".ruff_cache",
        tmp_path / "build",
        tmp_path / "dist",
        tmp_path / "src" / "pkg.egg-info",
    )
    for directory in generated_dirs:
        directory.mkdir(parents=True)
        (directory / "marker.txt").write_text("generated", encoding="utf-8")
    private_runtime_dir = tmp_path / "reports"
    private_runtime_dir.mkdir()
    (private_runtime_dir / "live.json").write_text("private", encoding="utf-8")

    removed = {path.as_posix() for path in release.cleanup_generated(tmp_path)}

    assert "src/pkg/__pycache__" in removed
    assert ".pytest_cache" in removed
    assert ".ruff_cache" in removed
    assert "build" in removed
    assert "dist" in removed
    assert "src/pkg.egg-info" in removed
    for directory in generated_dirs:
        assert not directory.exists()
    assert private_runtime_dir.exists()


def test_cleanup_rejects_paths_outside_package_root(tmp_path: Path) -> None:
    release = _load_release_module()

    outside_path = tmp_path.parent / "outside-generated"

    try:
        release._ensure_within_root(outside_path, tmp_path)
    except release.ReleaseError as exc:
        assert "outside package root" in str(exc)
    else:
        raise AssertionError("outside cleanup target was not rejected")


def test_scan_reports_generated_private_and_secret_findings(tmp_path: Path) -> None:
    release = _load_release_module()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "module.pyc").write_bytes(b"0")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "live.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".env").write_text("x=1", encoding="utf-8")
    (tmp_path / "src").mkdir()
    secret_line = "API" + "_KEY = " + '"example-value-1234"'
    (tmp_path / "src" / "settings.py").write_text(secret_line, encoding="utf-8")

    report = release.scan_tree(tmp_path, include_gitleaks=False)
    findings = {(item.path, item.category, item.reason) for item in report.findings}

    assert ("__pycache__", "generated", "generated release blocker") in findings
    assert ("reports", "private-path", "runtime reports") in findings
    assert (".env", "private-path", "environment file") in findings
    assert ("src/settings.py", "secret", "secret assignment") in findings


def test_scan_reports_sensitive_files_and_unquoted_secret_assignments(tmp_path: Path) -> None:
    release = _load_release_module()
    private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
    (tmp_path / "leak.pem").write_text(f"{private_key_header}\nabc\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    secret_line = "API" + "_KEY=" + "example-value-1234"
    (tmp_path / "src" / "settings.txt").write_text(secret_line, encoding="utf-8")

    report = release.scan_tree(tmp_path, include_gitleaks=False)
    findings = {(item.path, item.category, item.reason) for item in report.findings}

    assert ("leak.pem", "secret", "sensitive key/certificate file") in findings
    assert ("src/settings.txt", "secret", "secret assignment") in findings


def test_scan_cli_output_is_actionable_when_gitleaks_is_unavailable(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    release = _load_release_module()
    monkeypatch.setattr(release.shutil, "which", lambda _name: None)
    (tmp_path / "dist").mkdir()

    exit_code = release.run_scan(argparse.Namespace(path=str(tmp_path)))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "gitleaks: unavailable" in output
    assert "dist | generated | generated release blocker" in output


def test_gitleaks_unavailable_status_does_not_create_findings(tmp_path: Path, monkeypatch) -> None:
    release = _load_release_module()
    monkeypatch.setattr(release.shutil, "which", lambda _name: None)

    report = release.scan_tree(tmp_path)

    assert report.gitleaks_status == "gitleaks: unavailable (deterministic fallback scan ran)"
    assert report.findings == ()


def test_gitleaks_findings_include_reported_path_and_rule(tmp_path: Path, monkeypatch) -> None:
    release = _load_release_module()
    monkeypatch.setattr(release.shutil, "which", lambda _name: "gitleaks")

    def fake_run(command, **_kwargs):
        report_path = Path(command[command.index("--report-path") + 1])
        report_path.write_text(
            json.dumps(
                [
                    {
                        "File": "src/secrets.txt",
                        "RuleID": "generic-api-key",
                        "Description": "Generic API Key",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    report = release.scan_tree(tmp_path)
    findings = {(item.path, item.category, item.reason) for item in report.findings}

    assert report.gitleaks_status == "gitleaks: findings detected"
    assert ("src/secrets.txt", "secret", "generic-api-key: Generic API Key") in findings


def test_manifest_candidate_existing_file_returns_clean_error(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    release = _load_release_module()
    target = tmp_path / "candidate"
    target.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(release, "validate_manifest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(release, "find_unlisted_files", lambda **_kwargs: [])

    exit_code = release.run_manifest(argparse.Namespace(check=False, candidate=str(target)))

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "candidate target must be a directory" in captured.err
    assert "Traceback" not in captured.err


def test_verify_materializes_candidate_and_scans_candidate_and_live_scope(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    release = _load_release_module()
    calls: list[str] = []
    monkeypatch.setattr(
        release,
        "validate_manifest",
        lambda: [release.ManifestFile(path="pyproject.toml", category="package-metadata")],
    )
    monkeypatch.setattr(release, "find_unlisted_files", lambda **_kwargs: [])

    def fake_copy_candidate(target: Path) -> int:
        calls.append("copy")
        (target / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        return 1

    def fake_scan_tree(root: Path):
        if root == release.PACKAGE_ROOT:
            calls.append("scan-package")
        else:
            calls.append("scan-candidate")
            assert root != tmp_path
        return release.ScanReport(root=root, findings=(), gitleaks_status="gitleaks: skipped")

    monkeypatch.setattr(release, "copy_candidate", fake_copy_candidate)
    monkeypatch.setattr(release, "scan_tree", fake_scan_tree)

    exit_code = release.run_verify(argparse.Namespace())

    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls == ["copy", "scan-candidate", "scan-package"]
    assert "Candidate materialized:" in output
    assert "Candidate removed after verification." in output
    assert "Release verification passed." in output


def test_verify_fails_with_prefixed_scan_findings(capsys, monkeypatch) -> None:
    release = _load_release_module()
    monkeypatch.setattr(
        release,
        "validate_manifest",
        lambda: [release.ManifestFile(path="pyproject.toml", category="package-metadata")],
    )
    monkeypatch.setattr(release, "find_unlisted_files", lambda **_kwargs: [])
    monkeypatch.setattr(release, "copy_candidate", lambda _target: 1)

    def fake_scan_tree(root: Path):
        if root == release.PACKAGE_ROOT:
            return release.ScanReport(
                root=root,
                findings=(
                    release.ScanFinding(
                        path="leak.txt",
                        category="secret",
                        reason="secret assignment",
                    ),
                ),
                gitleaks_status="gitleaks: skipped",
            )
        return release.ScanReport(root=root, findings=(), gitleaks_status="gitleaks: skipped")

    monkeypatch.setattr(release, "scan_tree", fake_scan_tree)

    exit_code = release.run_verify(argparse.Namespace())

    combined_output = capsys.readouterr().out
    assert exit_code == 1
    assert "package:leak.txt | secret | secret assignment" in combined_output
