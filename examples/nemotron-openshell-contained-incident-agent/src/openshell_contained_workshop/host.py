"""Thin host-side launcher; no agent code executes in this module."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openshell import SandboxClient, SandboxSession

from .observability import redact_text

DEFAULT_SANDBOX_NAME = "contained-agent-workshop"
RESULT_PREFIX = "RESULT_PATH="
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
RUNTIME_ENV_ALLOWLIST = (
    "MODEL_PROVIDER",
    "NVIDIA_MODEL",
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "MODEL_TEMPERATURE",
    "MODEL_MAX_TOKENS",
    "LANGSMITH_TRACING",
    "LANGSMITH_PROJECT",
    "LANGSMITH_API_KEY",
    "LANGCHAIN_CALLBACKS_BACKGROUND",
    "LANGSMITH_OUTPUT_PREVIEW_CHARS",
    "OPENSHELL_DEFAULT_TIMEOUT_SECONDS",
)


def load_env_file(path: Path) -> list[str]:
    """Load a local dotenv file without printing or returning any values."""

    if not path.exists():
        raise FileNotFoundError(f"Missing {path.name}; copy .env.example to .env first.")
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded


def runtime_environment(
    *,
    sandbox_name: str,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the explicit environment allowlist injected into the agent process."""

    values = source or os.environ
    result = {name: values[name] for name in RUNTIME_ENV_ALLOWLIST if values.get(name)}
    result["OPENSHELL_SANDBOX_NAME"] = sandbox_name
    result["OPENSHELL_EXECUTION_BOUNDARY"] = "openshell-contained"
    return result


def _openshell_prefix() -> list[str]:
    executable = shutil.which("openshell")
    return [executable] if executable else ["uv", "run", "openshell"]


def _run_cli(args: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_openshell_prefix(), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _plain_process_output(process: subprocess.CompletedProcess[str]) -> str:
    return _ANSI_ESCAPE.sub("", f"{process.stdout}\n{process.stderr}")


def prepare_sandbox(
    *,
    example_root: Path,
    sandbox_name: str = DEFAULT_SANDBOX_NAME,
) -> str:
    """Create the custom-image sandbox, or safely reuse an existing one."""

    policy = example_root / "workshop/policies/contained-runtime.yaml"
    existing = _run_cli(["sandbox", "get", sandbox_name], timeout=60)
    if existing.returncode == 0:
        if "Phase: Error" in _plain_process_output(existing):
            raise RuntimeError(
                f"Sandbox {sandbox_name!r} is in an unrecoverable Error phase. "
                f"Delete it with 'openshell sandbox delete {sandbox_name}' and rerun this cell "
                "so OpenShell rebuilds the corrected image."
            )
        update = _run_cli(
            ["policy", "set", sandbox_name, "--policy", str(policy), "--wait"],
            timeout=180,
        )
        if update.returncode != 0:
            output = redact_text(f"{update.stdout}\n{update.stderr}", max_chars=2000)
            raise RuntimeError(f"Could not refresh the contained-runtime policy: {output}")
        return "reused"

    created = _run_cli(
        [
            "sandbox",
            "create",
            "--name",
            sandbox_name,
            "--from",
            str(example_root),
            "--policy",
            str(policy),
            "--no-tty",
            "--",
            "true",
        ],
        timeout=900,
    )
    if created.returncode != 0:
        output = redact_text(f"{created.stdout}\n{created.stderr}", max_chars=3000)
        raise RuntimeError(f"Could not create the contained-agent sandbox: {output}")
    return "created"


def open_session(sandbox_name: str = DEFAULT_SANDBOX_NAME) -> tuple[SandboxClient, SandboxSession]:
    """Open a host-side SDK session to an existing ready sandbox."""

    client = SandboxClient.from_active_cluster()
    client.get(sandbox_name)
    ref = client.wait_ready(sandbox_name)
    return client, SandboxSession(client, ref)


def invoke_contained_agent(
    session: SandboxSession,
    *,
    prompt: str,
    lab: str,
    sandbox_name: str = DEFAULT_SANDBOX_NAME,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Invoke the sandbox-resident runner and return its structured result."""

    run_id = uuid.uuid4()
    request = {
        "lab": lab,
        "prompt": prompt,
        "run_id": str(run_id),
        "thread_id": f"contained-{lab}-{run_id.hex[:8]}",
    }
    process = session.exec(
        ["/app/.venv/bin/python", "-m", "openshell_contained_workshop.runner"],
        workdir="/app",
        env=runtime_environment(sandbox_name=sandbox_name),
        stdin=json.dumps(request).encode("utf-8"),
        timeout_seconds=timeout_seconds,
    )
    combined = "\n".join(part for part in (process.stdout, process.stderr) if part)
    result_paths = [
        line.removeprefix(RESULT_PREFIX).strip()
        for line in combined.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if not result_paths:
        output = redact_text(combined, max_chars=2500)
        raise RuntimeError(
            f"Contained runner exited with {process.exit_code} without a result path: {output}"
        )
    result_path = result_paths[-1]
    if not re.fullmatch(r"/sandbox/results/[a-z0-9-]+-[0-9a-f-]+\.json", result_path):
        raise RuntimeError("Contained runner returned an invalid result path.")
    readback = session.exec(["cat", result_path], timeout_seconds=60)
    if readback.exit_code != 0:
        raise RuntimeError(f"Could not read contained result at {result_path}")
    result = json.loads(readback.stdout)
    result["runner_exit_code"] = process.exit_code
    return result
