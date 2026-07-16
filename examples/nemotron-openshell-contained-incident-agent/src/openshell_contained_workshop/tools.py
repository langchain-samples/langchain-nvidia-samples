"""Tools executed by the Deep Agent from inside its OpenShell sandbox."""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
from pathlib import Path
from textwrap import dedent

from langchain_core.tools import tool

from .backend import ContainedRuntimeBackend

ANALYSIS_SCRIPT = dedent(
    r'''
    from collections import Counter, defaultdict
    import json
    from pathlib import Path
    import shlex

    log_path = Path("/sandbox/sample_app.log")
    summary_path = Path("/sandbox/incident_summary.json")
    report_path = Path("/sandbox/incident_report.md")

    records = []
    for raw_line in log_path.read_text(encoding="utf-8").splitlines():
        parts = shlex.split(raw_line)
        record = {"timestamp": parts[0]}
        for part in parts[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            record[key] = int(value) if key in {"status", "latency_ms"} else value
        records.append(record)

    failures = [r for r in records if int(r.get("status", 0)) >= 500]
    warnings = [r for r in records if r.get("level") == "WARN"]
    slowest = sorted(records, key=lambda r: int(r.get("latency_ms", 0)), reverse=True)[:5]
    level_counts = Counter(r.get("level", "unknown") for r in records)
    service_counts = Counter(r.get("service", "unknown") for r in records)
    status_counts = Counter(str(r.get("status", "unknown")) for r in records)
    failing_endpoints = Counter(r.get("path", "unknown") for r in failures)

    latencies_by_service = defaultdict(list)
    for record in records:
        latencies_by_service[record.get("service", "unknown")].append(
            int(record.get("latency_ms", 0))
        )
    p95_latency_by_service = {}
    for service, latencies in latencies_by_service.items():
        ordered = sorted(latencies)
        index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
        p95_latency_by_service[service] = ordered[index]

    summary = {
        "total_records": len(records),
        "level_counts": dict(level_counts),
        "service_counts": dict(service_counts),
        "status_counts": dict(status_counts),
        "top_failing_endpoints": failing_endpoints.most_common(5),
        "slowest_requests": slowest,
        "p95_latency_by_service_ms": p95_latency_by_service,
        "first_failure_timestamp": failures[0]["timestamp"] if failures else None,
        "last_failure_timestamp": failures[-1]["timestamp"] if failures else None,
        "level_error_count": level_counts.get("ERROR", 0),
        "http_5xx_count": len(failures),
        "warning_count": len(warnings),
        "suspected_cause": "inventory database timeouts caused checkout failures",
        "execution_boundary": "openshell-contained",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# Incident Report", "", "## Executive Summary",
        f"The log contains {level_counts.get('ERROR', 0)} level=ERROR records, "
        f"{len(failures)} HTTP 5xx responses, and {len(warnings)} warnings. "
        "Inventory database timeouts cascaded into checkout failures.",
        "", "## Evidence",
        f"- First HTTP failure: {summary['first_failure_timestamp']}",
        f"- Last HTTP failure: {summary['last_failure_timestamp']}",
        f"- Level counts: {summary['level_counts']}",
        f"- Status counts: {summary['status_counts']}",
        f"- Top failing endpoints: {summary['top_failing_endpoints']}",
        f"- P95 latency by service: {summary['p95_latency_by_service_ms']}",
        "", "## Timeline",
    ]
    for record in failures[:8]:
        report.append(
            f"- {record['timestamp']} {record.get('service')} {record.get('path')} "
            f"status={record.get('status')} latency_ms={record.get('latency_ms')} "
            f"message={record.get('message')}"
        )
    report.extend([
        "", "## Suspected Cause",
        "Inventory database timeouts increased latency and returned 503 responses. "
        "Checkout then failed because it depends on inventory availability.",
        "", "## Recommended Next Actions",
        "- Inspect inventory database health, connection pools, and recent deploys.",
        "- Add checkout fallback behavior for temporary inventory unavailability.",
        "- Alert on inventory p95 latency and 5xx rate before checkout impact.",
        "- Compare this contained-runtime trace with a healthy run in LangSmith.", "",
    ])
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "report_path": str(report_path)}))
    '''
).strip()


def runtime_snapshot() -> dict[str, object]:
    """Return non-secret evidence about the current OpenShell-contained process."""

    return {
        "execution_boundary": os.getenv(
            "OPENSHELL_EXECUTION_BOUNDARY",
            "openshell-contained",
        ),
        "sandbox_name": os.getenv("OPENSHELL_SANDBOX_NAME", "<runtime-hostname>"),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "cwd": str(Path.cwd()),
        "architecture": platform.machine(),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
    }


@tool
def inspect_runtime_boundary() -> str:
    """Show evidence that the agent and its executable are inside OpenShell."""

    return json.dumps(runtime_snapshot(), indent=2, sort_keys=True)


@tool
def run_contained_smoke_test() -> str:
    """Run OS and Python checks in the same OpenShell runtime as the agent."""

    backend = ContainedRuntimeBackend()
    result = backend.execute(
        "uname -a\n"
        "python3 --version\n"
        "printf 'hostname=' && hostname\n"
        "printf 'pid=' && printf '%s\\n' $$\n"
        "printf 'cwd=' && pwd"
    )
    if result.exit_code != 0:
        raise RuntimeError(f"Contained smoke test failed with exit code {result.exit_code}")
    return result.output


@tool
def analyze_incident_log() -> str:
    """Analyze the fixture entirely inside the agent's current OpenShell sandbox."""

    backend = ContainedRuntimeBackend()
    log_bytes = Path("/app/workshop/data/sample_app.log").read_bytes()
    uploads = backend.upload_files(
        [
            ("/sandbox/sample_app.log", log_bytes),
            ("/sandbox/analyze_incident.py", ANALYSIS_SCRIPT.encode("utf-8")),
        ]
    )
    failures = [item.path for item in uploads if item.error is not None]
    if failures:
        raise RuntimeError(f"Could not prepare incident analysis files: {failures}")

    script = backend.execute("python3 /sandbox/analyze_incident.py")
    if script.exit_code != 0:
        raise RuntimeError(
            f"Incident analysis failed with exit code {script.exit_code}: {script.output}"
        )
    readback = backend.execute(
        "python3 -m json.tool /sandbox/incident_summary.json\n"
        "sed -n '1,100p' /sandbox/incident_report.md"
    )
    if readback.exit_code != 0:
        raise RuntimeError(f"Incident artifact readback failed: {readback.output}")
    return "\n".join(part for part in (script.output, readback.output) if part)


@tool
def run_policy_boundary_demo() -> str:
    """Demonstrate one allowed and one policy-denied write inside OpenShell."""

    backend = ContainedRuntimeBackend()
    commands = {
        "runtime_identity_and_home_permissions": (
            "id\n"
            "stat -c 'home_owner=%U home_mode=%A' /home/sandbox"
        ),
        "allowed_sandbox_write": (
            "printf 'allowed\\n' > /sandbox/policy_allowed.txt "
            "&& cat /sandbox/policy_allowed.txt"
        ),
        "expected_policy_denied_home_write": (
            "printf 'denied\\n' > /home/sandbox/policy_denied.txt"
        ),
    }
    sections = []
    for label, command in commands.items():
        result = backend.execute(command, timeout=120)
        sections.append(
            "\n".join(
                [
                    f"## {label}",
                    f"command: {command}",
                    f"exit_code: {result.exit_code}",
                    "output:",
                    result.output or "<no output>",
                ]
            )
        )
    return "\n\n".join(sections)
