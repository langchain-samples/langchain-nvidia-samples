#!/usr/bin/env python3
"""Preflight checks that never print secret values."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_MISSING_VALUES = {"", "...", "changeme", "change-me", "todo", "your-key-here"}


def _status(name: str, ok: bool, detail: str = "") -> None:
    marker = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    print(f"[{marker}] {name}{suffix}")


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _docker_running() -> bool:
    if not _command_exists("docker"):
        return False
    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _openshell_gateway_reachable() -> bool:
    result = subprocess.run(
        ["openshell", "status"],
        text=True,
        capture_output=True,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", f"{result.stdout}\n{result.stderr}")
    if result.returncode != 0:
        return False
    blocked_markers = (
        "No gateway configured",
        "Set one with: openshell gateway select",
        "Register a gateway with:",
        "failed to connect",
        "connection refused",
    )
    return not any(marker in output for marker in blocked_markers)


def _print_gateway_help() -> None:
    print()
    print("OpenShell gateway help:")
    print("- Docker can be running while OpenShell is still not ready.")
    print("- The repo needs a selected OpenShell gateway before it can create sandboxes.")
    print("- Check with: uv run openshell status")
    print("- If status says no gateway is configured, register/select one, then rerun this script.")


def _load_dotenv_names(path: Path) -> dict[str, str]:
    """Read .env enough to check presence, without printing values."""

    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("'\"")
        if name:
            values[name] = value
    return values


def _configured(name: str, dotenv: dict[str, str]) -> bool:
    value = os.getenv(name, dotenv.get(name, ""))
    return value.strip().lower() not in _MISSING_VALUES


def _module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def main() -> int:
    failures = 0

    python_ok = sys.version_info >= (3, 12)
    _status("Python >= 3.12", python_ok, sys.version.split()[0])
    failures += 0 if python_ok else 1

    for command in ("uv", "docker"):
        ok = _command_exists(command)
        _status(f"{command} on PATH", ok)
        failures += 0 if ok else 1

    docker_ok = _docker_running()
    _status("Docker daemon running", docker_ok)
    failures += 0 if docker_ok else 1

    for module in (
        "deepagents",
        "langchain",
        "langchain_nvidia_ai_endpoints",
        "langsmith",
        "openshell",
    ):
        ok = _module_available(module)
        _status(f"Python package {module}", ok)
        failures += 0 if ok else 1

    gateway_ok = _openshell_gateway_reachable()
    _status("OpenShell gateway reachable", gateway_ok)
    failures += 0 if gateway_ok else 1

    env_file = Path(".env")
    dotenv = _load_dotenv_names(env_file)
    _status(".env file present", env_file.exists(), "values are checked but never printed")
    failures += 0 if env_file.exists() else 1

    provider = os.getenv("MODEL_PROVIDER", dotenv.get("MODEL_PROVIDER", "nvidia")).strip().lower()
    _status("MODEL_PROVIDER configured", provider in {"nvidia", "langchain"}, provider or "missing")
    failures += 0 if provider in {"nvidia", "langchain"} else 1

    required = [
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "LANGSMITH_API_KEY",
        "OPENSHELL_SANDBOX_NAME",
    ]
    if provider == "nvidia":
        required.extend(["NVIDIA_MODEL", "NVIDIA_API_KEY"])
    else:
        required.append("AGENT_MODEL")

    for name in required:
        ok = _configured(name, dotenv)
        _status(f"{name} configured", ok)
        failures += 0 if ok else 1

    print()
    if failures:
        if not gateway_ok:
            _print_gateway_help()
            print()
        print("Preflight found blocking local prerequisites. Fix those, then rerun this script.")
        return 1
    print("Preflight looks ready. Secret values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
