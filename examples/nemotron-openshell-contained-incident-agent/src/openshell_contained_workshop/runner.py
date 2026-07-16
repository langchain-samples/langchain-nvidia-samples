"""Machine-readable entrypoint executed inside the OpenShell sandbox."""

from __future__ import annotations

import json
import re
import sys
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .agent import build_agent
from .observability import redact_text
from .tools import runtime_snapshot

LAB_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
THREAD_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
RESULT_ROOT = Path("/sandbox/results")
LAB_ARTIFACTS = {
    "incident-analysis": (
        Path("/sandbox/incident_summary.json"),
        Path("/sandbox/incident_report.md"),
    ),
    "generic-execution": (Path("/sandbox/generic_contained_demo.py"),),
    "policy-enforcement": (Path("/sandbox/policy_allowed.txt"),),
}


def validate_request(payload: Mapping[str, Any]) -> dict[str, str]:
    """Validate the non-secret JSON request received on stdin."""

    lab = str(payload.get("lab", ""))
    prompt = str(payload.get("prompt", ""))
    thread_id = str(payload.get("thread_id", ""))
    run_id = str(payload.get("run_id", ""))
    if not LAB_PATTERN.fullmatch(lab):
        raise ValueError("lab must be a lowercase slug up to 64 characters")
    if not prompt.strip() or len(prompt) > 20_000:
        raise ValueError("prompt must contain 1 to 20000 characters")
    if not THREAD_PATTERN.fullmatch(thread_id):
        raise ValueError("thread_id contains unsupported characters")
    try:
        uuid.UUID(run_id)
    except ValueError as exc:
        raise ValueError("run_id must be a UUID") from exc
    return {"lab": lab, "prompt": prompt, "thread_id": thread_id, "run_id": run_id}


def final_text(result: Mapping[str, Any]) -> str:
    """Extract the final assistant message from a Deep Agent result."""

    messages = result.get("messages") or []
    if not messages:
        return ""
    message = messages[-1]
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(str(part) for part in content)
    return str(content or "")


def _artifact_paths(lab: str) -> list[str]:
    """Return artifacts produced by this lab, not files left by earlier labs."""

    candidates = LAB_ARTIFACTS.get(lab, ())
    return [str(path) for path in candidates if path.exists()]


def _write_record(record: Mapping[str, Any], *, result_root: Path) -> Path:
    result_root.mkdir(parents=True, exist_ok=True)
    path = result_root / f"{record['lab']}-{record['run_id']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path


def run_request(
    payload: Mapping[str, Any],
    *,
    agent_factory: Callable[[], Any] = build_agent,
    result_root: Path = RESULT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    """Run one parent-agent invocation and persist a structured result."""

    request = validate_request(payload)
    config = {
        "configurable": {"thread_id": request["thread_id"]},
        "run_id": uuid.UUID(request["run_id"]),
        "run_name": f"contained-workshop-{request['lab']}",
        "tags": ["workshop", "openshell-contained", request["lab"], "incident-analysis"],
        "metadata": {
            "workshop": "openshell-contained-agent",
            "lab": request["lab"],
            "execution_boundary": "openshell-contained",
            "sandbox_name": runtime_snapshot()["sandbox_name"],
        },
    }
    try:
        agent = agent_factory()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request["prompt"]}]},
            config=config,
        )
        record: dict[str, Any] = {
            "status": "ok",
            "lab": request["lab"],
            "run_id": request["run_id"],
            "thread_id": request["thread_id"],
            "final_text": final_text(result),
            "runtime": runtime_snapshot(),
            "artifacts": _artifact_paths(request["lab"]),
        }
    except Exception as exc:  # noqa: BLE001 - boundary must serialize failures
        record = {
            "status": "error",
            "lab": request["lab"],
            "run_id": request["run_id"],
            "thread_id": request["thread_id"],
            "error": redact_text(f"{type(exc).__name__}: {exc}", max_chars=2000),
            "runtime": runtime_snapshot(),
            "artifacts": _artifact_paths(request["lab"]),
        }
    return _write_record(record, result_root=result_root), record


def main() -> int:
    """Read one request from stdin and print only its sandbox result path marker."""

    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("request must be a JSON object")
        result_path, record = run_request(payload)
    except Exception as exc:  # noqa: BLE001 - CLI validation boundary
        print(f"runner-error: {redact_text(exc, max_chars=1000)}", file=sys.stderr)
        return 2
    print(f"RESULT_PATH={result_path}")
    return 0 if record["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
