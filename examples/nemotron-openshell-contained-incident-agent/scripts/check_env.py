#!/usr/bin/env python3
"""Preflight checks that report configuration presence but never secret values."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_MISSING = {"", "...", "changeme", "change-me", "todo", "your-key-here"}


def _status(name: str, ok: bool, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[{'OK' if ok else 'MISSING'}] {name}{suffix}")


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _docker_running() -> bool:
    if not _command_exists("docker"):
        return False
    return (
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _gateway_reachable() -> bool:
    if not _command_exists("openshell"):
        return False
    result = subprocess.run(
        ["openshell", "status"],
        text=True,
        capture_output=True,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", f"{result.stdout}\n{result.stderr}")
    blockers = (
        "No gateway configured",
        "Set one with: openshell gateway select",
        "Register a gateway with:",
        "failed to connect",
        "connection refused",
    )
    return result.returncode == 0 and not any(marker in output for marker in blockers)


def _print_gateway_help() -> None:
    print()
    print("OpenShell gateway help:")
    print("- Docker can be running while OpenShell is still not ready.")
    print("- Check the selected gateway with: uv run openshell status")
    print("- Start/register/select a gateway, then rerun this preflight.")


def _dotenv_names(path: Path) -> dict[str, bool]:
    names: dict[str, bool] = {}
    if not path.exists():
        return names
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        names[name.strip()] = value.strip().strip("'\"").lower() not in _MISSING
    return names


def main() -> int:
    failures = 0
    gateway_ok = _gateway_reachable()
    checks = {
        "Python >= 3.12": sys.version_info >= (3, 12),
        "uv on PATH": _command_exists("uv"),
        "docker on PATH": _command_exists("docker"),
        "Docker daemon running": _docker_running(),
        "openshell on PATH": _command_exists("openshell"),
        "OpenShell gateway reachable": gateway_ok,
    }
    for label, ok in checks.items():
        _status(label, ok)
        failures += 0 if ok else 1

    for module in (
        "deepagents",
        "langchain",
        "langchain_nvidia_ai_endpoints",
        "langsmith",
        "openshell",
    ):
        ok = importlib.util.find_spec(module) is not None
        _status(f"Python package {module}", ok)
        failures += 0 if ok else 1

    for path in (
        Path("Dockerfile"),
        Path(".dockerignore"),
        Path("workshop/data/sample_app.log"),
        Path("workshop/policies/contained-runtime.yaml"),
        Path("workshop/notebooks/participant_walkthrough.ipynb"),
    ):
        ok = path.exists()
        _status(str(path), ok)
        failures += 0 if ok else 1

    env_path = Path(".env")
    configured = _dotenv_names(env_path)
    _status(".env file present", env_path.exists(), "values are never printed")
    failures += 0 if env_path.exists() else 1
    for name in (
        "MODEL_PROVIDER",
        "NVIDIA_MODEL",
        "NVIDIA_API_KEY",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "LANGSMITH_API_KEY",
        "OPENSHELL_SANDBOX_NAME",
    ):
        ok = bool(os.getenv(name)) or configured.get(name, False)
        _status(f"{name} configured", ok)
        failures += 0 if ok else 1

    print()
    if failures:
        if not gateway_ok:
            _print_gateway_help()
        print()
        print("Preflight found blocking prerequisites. Fix them before running live labs.")
        return 1
    print("Preflight looks ready. No secret values were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
