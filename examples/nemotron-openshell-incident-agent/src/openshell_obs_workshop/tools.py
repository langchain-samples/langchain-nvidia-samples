"""Workshop tools exposed to the Deep Agent."""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

from langchain_core.tools import tool
from openshell import SandboxClient, SandboxSession

from .backend import SANDBOX_NAME_ENV
from .observability import end_trace, optional_trace, redact_text

ANALYSIS_SCRIPT = dedent(
    r'''
    from __future__ import annotations

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
            if key in {"status", "latency_ms"}:
                record[key] = int(value)
            else:
                record[key] = value
        records.append(record)

    errors = [r for r in records if r.get("level") == "ERROR" or int(r.get("status", 0)) >= 500]
    warnings = [r for r in records if r.get("level") == "WARN"]
    slowest = sorted(records, key=lambda r: int(r.get("latency_ms", 0)), reverse=True)[:5]

    level_counts = Counter(r.get("level", "unknown") for r in records)
    service_counts = Counter(r.get("service", "unknown") for r in records)
    status_counts = Counter(str(r.get("status", "unknown")) for r in records)
    failing_endpoints = Counter(r.get("path", "unknown") for r in errors)

    latencies_by_service = defaultdict(list)
    for record in records:
        latencies_by_service[record.get("service", "unknown")].append(int(record.get("latency_ms", 0)))

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
        "first_error_timestamp": errors[0]["timestamp"] if errors else None,
        "last_error_timestamp": errors[-1]["timestamp"] if errors else None,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "suspected_cause": "inventory database timeouts caused checkout failures",
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# Incident Report",
        "",
        "## Executive Summary",
        (
            f"The log contains {len(errors)} error records and {len(warnings)} warnings. "
            "The likely incident was inventory database timeout behavior that cascaded "
            "into checkout failures."
        ),
        "",
        "## Evidence",
        f"- First error: {summary['first_error_timestamp']}",
        f"- Last error: {summary['last_error_timestamp']}",
        f"- Level counts: {summary['level_counts']}",
        f"- Status counts: {summary['status_counts']}",
        f"- Top failing endpoints: {summary['top_failing_endpoints']}",
        f"- P95 latency by service: {summary['p95_latency_by_service_ms']}",
        "",
        "## Timeline",
    ]
    for record in errors[:8]:
        report.append(
            f"- {record['timestamp']} {record.get('service')} {record.get('path')} "
            f"status={record.get('status')} latency_ms={record.get('latency_ms')} "
            f"message={record.get('message')}"
        )
    report.extend(
        [
            "",
            "## Suspected Cause",
            "Inventory service database timeouts increased latency and returned 503/504 responses. "
            "Checkout requests then failed because they depended on inventory availability.",
            "",
            "## Recommended Next Actions",
            "- Inspect inventory database health, connection pools, and recent deploys.",
            "- Add checkout fallback behavior for temporary inventory unavailability.",
            "- Alert on inventory p95 latency and 5xx rate before checkout impact.",
            "- Compare this trace with a healthy run in LangSmith.",
            "",
        ]
    )
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "report_path": str(report_path)}))
    '''
).strip()


def _sandbox_session() -> SandboxSession:
    sandbox_name = os.environ.get(SANDBOX_NAME_ENV, "workshop-sandbox")
    client = SandboxClient.from_active_cluster()
    client.get(sandbox_name)
    ref = client.wait_ready(sandbox_name)
    return SandboxSession(client, ref)


@tool
def run_sandbox_smoke_test() -> str:
    """Run uname and python version checks inside the OpenShell sandbox."""

    session = _sandbox_session()
    commands = {
        "uname": "uname -a",
        "python": "python3 --version",
    }
    results: list[str] = []

    with optional_trace(
        name="openshell.sandbox_smoke_test",
        run_type="tool",
        inputs={"commands": commands, "sandbox_name": os.environ.get(SANDBOX_NAME_ENV)},
        tags=["openshell", "sandbox", "smoke-test"],
        metadata={"sandbox_id": session.id},
    ) as run:
        for label, command in commands.items():
            result = session.exec(
                ["bash", "-lc", "bash -s"],
                stdin=command.encode("utf-8"),
                timeout_seconds=60,
            )
            combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            results.append(
                "\n".join(
                    [
                        f"## {label}",
                        f"command: {command}",
                        f"exit_code: {result.exit_code}",
                        "output:",
                        combined_output or "<no output>",
                    ]
                )
            )
        output = "\n\n".join(results)
        end_trace(run, outputs={"output_preview": redact_text(output, max_chars=1200)})
        return output


@tool
def analyze_incident_log() -> str:
    """Analyze the sample application log by running Python in OpenShell."""

    log_path = Path("workshop/data/sample_app.log")
    log_text = log_path.read_text(encoding="utf-8")
    session = _sandbox_session()

    with optional_trace(
        name="openshell.incident_analysis",
        run_type="tool",
        inputs={"log_path": str(log_path), "sandbox_name": os.environ.get(SANDBOX_NAME_ENV)},
        tags=["openshell", "sandbox", "incident-analysis"],
        metadata={"sandbox_id": session.id},
    ) as run:
        session.exec(
            ["bash", "-lc", "mkdir -p /sandbox && cat > /sandbox/sample_app.log"],
            stdin=log_text.encode("utf-8"),
            timeout_seconds=60,
        )
        session.exec(
            ["bash", "-lc", "cat > /sandbox/analyze_incident.py"],
            stdin=ANALYSIS_SCRIPT.encode("utf-8"),
            timeout_seconds=60,
        )
        script_result = session.exec(
            ["python3", "/sandbox/analyze_incident.py"],
            timeout_seconds=int(os.getenv("OPENSHELL_DEFAULT_TIMEOUT_SECONDS", "1800")),
        )
        report_result = session.exec(
            ["cat", "/sandbox/incident_report.md"],
            timeout_seconds=60,
        )
        output = "\n".join(
            part
            for part in (
                script_result.stdout,
                script_result.stderr,
                report_result.stdout,
                report_result.stderr,
            )
            if part
        )
        end_trace(
            run,
            outputs={
                "script_exit_code": script_result.exit_code,
                "report_exit_code": report_result.exit_code,
                "output_preview": redact_text(output, max_chars=1000),
            },
        )
        if script_result.exit_code != 0:
            msg = f"Incident analysis script failed with exit code {script_result.exit_code}:\n{output}"
            raise RuntimeError(msg)
        if report_result.exit_code != 0:
            msg = f"Incident report readback failed with exit code {report_result.exit_code}:\n{output}"
            raise RuntimeError(msg)
        return output


@tool
def run_policy_boundary_demo() -> str:
    """Run the workshop's allowed/denied OpenShell filesystem policy demo."""

    session = _sandbox_session()
    commands = {
        "allowed_sandbox_write": "printf 'allowed\\n' > /sandbox/policy_allowed.txt && cat /sandbox/policy_allowed.txt",
        "expected_denied_etc_write": "printf 'denied\\n' > /etc/policy_denied.txt",
    }
    results: list[str] = []

    with optional_trace(
        name="openshell.policy_boundary_demo",
        run_type="tool",
        inputs={"commands": commands, "sandbox_name": os.environ.get(SANDBOX_NAME_ENV)},
        tags=["openshell", "sandbox", "policy"],
        metadata={"sandbox_id": session.id},
    ) as run:
        for label, command in commands.items():
            result = session.exec(
                ["bash", "-lc", "bash -s"],
                stdin=command.encode("utf-8"),
                timeout_seconds=120,
            )
            combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            results.append(
                "\n".join(
                    [
                        f"## {label}",
                        f"command: {command}",
                        f"exit_code: {result.exit_code}",
                        "output:",
                        combined_output or "<no output>",
                    ]
                )
            )

        output = "\n\n".join(results)
        end_trace(run, outputs={"output_preview": redact_text(output, max_chars=1200)})
        return output
