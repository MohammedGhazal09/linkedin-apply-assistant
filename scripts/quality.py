from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DISTRIBUTION = "linkedin-apply-assistant"
AUDIT_EXTRAS = ("dev",)
AUDIT_REQUIREMENTS_PLACEHOLDER = "<installed-dev-dependency-closure>"


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]

    @property
    def display_command(self) -> str:
        return " ".join(self.command)


def build_gates() -> tuple[Gate, ...]:
    return (
        Gate("compile", ("python", "-m", "compileall", "-q", "src", "tests")),
        Gate("pytest", ("python", "-m", "pytest", "tests", "-q")),
        Gate("ruff check", ("python", "-m", "ruff", "check", "--no-cache", "src", "tests")),
        Gate(
            "ruff format",
            ("python", "-m", "ruff", "format", "--check", "--no-cache", "src", "tests"),
        ),
        Gate(
            "dependency audit",
            (
                "python",
                "-m",
                "pip_audit",
                "--requirement",
                AUDIT_REQUIREMENTS_PLACEHOLDER,
                "--no-deps",
                "--progress-spinner",
                "off",
            ),
        ),
    )


def _command_to_executable(command: tuple[str, ...]) -> list[str]:
    if command[:2] == ("python", "-m"):
        return [sys.executable, *command[1:]]
    return list(command)


def _marker_applies(marker: object, extras: set[str]) -> bool:
    if marker is None:
        return True

    from packaging.markers import default_environment

    env = default_environment()
    for extra in extras | {""}:
        env["extra"] = extra
        if marker.evaluate(env):  # type: ignore[attr-defined]
            return True
    return False


def _installed_distributions() -> dict[str, metadata.Distribution]:
    from packaging.utils import canonicalize_name

    distributions: dict[str, metadata.Distribution] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            distributions[canonicalize_name(name)] = distribution
    return distributions


def _iter_requirements(
    distribution: metadata.Distribution,
    extras: set[str],
) -> list[tuple[str, set[str]]]:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    requirements: list[tuple[str, set[str]]] = []
    for raw_requirement in distribution.requires or []:
        requirement = Requirement(raw_requirement)
        if _marker_applies(requirement.marker, extras):
            requirements.append((canonicalize_name(requirement.name), set(requirement.extras)))
    return requirements


def build_installed_dependency_pins(
    project_name: str = PROJECT_DISTRIBUTION,
    extras: Sequence[str] = AUDIT_EXTRAS,
) -> list[str]:
    """Return pinned installed dependencies for the package plus selected extras."""

    from packaging.utils import canonicalize_name

    distributions = _installed_distributions()
    project_key = canonicalize_name(project_name)
    project = distributions.get(project_key)
    if project is None:
        raise RuntimeError(
            f"{project_name!r} is not installed. Run: python -m pip install -e \".[dev]\""
        )

    queue = deque(_iter_requirements(project, set(extras)))
    processed_extras: dict[str, set[str]] = {}
    pins: dict[str, tuple[str, str]] = {}

    while queue:
        dependency_name, requested_extras = queue.popleft()
        if dependency_name == project_key:
            continue

        dependency = distributions.get(dependency_name)
        if dependency is None:
            raise RuntimeError(
                f"Required dependency {dependency_name!r} is not installed. "
                "Run: python -m pip install -e \".[dev]\""
            )

        package_name = canonicalize_name(dependency.metadata.get("Name", dependency_name))
        pins[dependency_name] = (package_name, dependency.version)

        extras_to_process = requested_extras | {""}
        already_processed = processed_extras.setdefault(dependency_name, set())
        new_extras = extras_to_process - already_processed
        if not new_extras:
            continue
        already_processed.update(new_extras)

        queue.extend(_iter_requirements(dependency, new_extras))

    return [f"{name}=={version}" for name, version in sorted(pins.values())]


def write_audit_requirements() -> Path:
    pins = build_installed_dependency_pins()
    if not pins:
        raise RuntimeError("No installed dependencies found for dependency audit.")

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        encoding="utf-8",
        prefix="linkedin-apply-assistant-audit-",
        suffix=".txt",
    ) as handle:
        handle.write("\n".join(pins))
        handle.write("\n")
        return Path(handle.name)


def _cleanup_temp_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def prepare_gate_command(gate: Gate) -> tuple[list[str], str, tuple[Path, ...]]:
    if gate.name != "dependency audit":
        return _command_to_executable(gate.command), gate.display_command, ()

    requirements_file = write_audit_requirements()
    cache_dir = Path(tempfile.mkdtemp(prefix="linkedin-apply-assistant-pip-audit-cache-"))
    command = (
        "python",
        "-m",
        "pip_audit",
        "--requirement",
        str(requirements_file),
        "--no-deps",
        "--progress-spinner",
        "off",
        "--cache-dir",
        str(cache_dir),
    )
    return _command_to_executable(command), " ".join(command), (requirements_file, cache_dir)


def list_gates(gates: Sequence[Gate]) -> None:
    for index, gate in enumerate(gates, start=1):
        print(f"{index}. {gate.name}: {gate.display_command}")


def run_gate(gate: Gate) -> int:
    cleanup_paths: tuple[Path, ...] = ()
    try:
        executable_command, display_command, cleanup_paths = prepare_gate_command(gate)
        print(f"\n== {gate.name} ==", flush=True)
        print(f"$ {display_command}", flush=True)
        result = subprocess.run(executable_command, cwd=PACKAGE_ROOT, check=False)
        return result.returncode
    except RuntimeError as exc:
        print(f"\nGate failed: {gate.name}: {exc}", file=sys.stderr)
        return 1
    finally:
        for path in cleanup_paths:
            _cleanup_temp_path(path)



def run_gates(gates: Sequence[Gate]) -> int:
    for gate in gates:
        exit_code = run_gate(gate)
        if exit_code != 0:
            print(f"\nGate failed: {gate.name} (exit {exit_code})", file=sys.stderr)
            return exit_code
    print("\nAll quality gates passed.")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone package quality gates.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print planned quality gates without executing them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    gates = build_gates()
    if args.list:
        list_gates(gates)
        return 0
    return run_gates(gates)


if __name__ == "__main__":
    raise SystemExit(main())
