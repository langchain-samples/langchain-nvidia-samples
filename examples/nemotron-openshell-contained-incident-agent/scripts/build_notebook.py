#!/usr/bin/env python3
"""Build the participant notebook from readable cell sources."""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path("workshop/notebooks/participant_walkthrough.ipynb")


def lines(source: str) -> list[str]:
    return source.strip("\n").splitlines(keepends=True)


def markdown(source: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": lines(source)}


def code(source: str, *, tags: list[str] | None = None) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"tags": tags or []},
        "outputs": [],
        "source": lines(source),
    }


cells = [
    markdown(
        """
# NVIDIA OpenShell Contained Deep Agent Workshop

In this workshop, OpenShell contains the **agent itself**: the parent Deep Agent
orchestrator, its subagents, model client, tools, generated Python, and artifacts.
This notebook stays outside as a thin provisioning and display surface.

```mermaid
flowchart LR
    Notebook[Host notebook] -->|provision + JSON request| Sandbox[OpenShell sandbox]
    subgraph Sandbox
        Runner[Contained runner] --> Parent[Parent Deep Agent]
        Parent --> Incident[Incident analyst]
        Parent --> Policy[Policy analyst]
        Parent --> Observability[Observability coach]
        Incident --> Exec[Python and shell]
        Exec --> Artifacts[/sandbox artifacts]
    end
    Parent --> NIM[NVIDIA NIM]
    Parent --> LS[LangSmith]
```

Each lab starts a new parent-agent run and therefore creates a separate LangSmith
root trace. The labs reuse one OpenShell sandbox, so files under `/sandbox` persist
until that sandbox is deleted.
"""
    ),
    markdown(
        """
## What You Will Learn

1. Build a locked OpenShell image containing the Deep Agents application.
2. Compare host and sandbox runtime evidence.
3. Delegate incident analysis while the parent and subagent share one sandbox boundary.
4. Distinguish model conclusions from deterministic artifact evidence.
5. Compare an allowed write with a policy-denied write for a user-owned directory.
6. Debug parent, subagent, tool, and command activity from direct LangSmith links.
"""
    ),
    markdown(
        "## 0. Host Setup\n\n"
        "This cell intentionally runs on the host. Record its hostname, PID, Python, "
        "and working directory so the contained-runtime evidence has a concrete baseline. "
        "The notebook never constructs or imports the Deep Agent."
    ),
    code(
        """
import json
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


def find_example_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "Dockerfile").exists():
            return candidate.resolve()
    raise RuntimeError("Open this notebook from inside the contained-agent example folder.")


ROOT = find_example_root(Path.cwd())
os.chdir(ROOT)
host_evidence = {
    "hostname": socket.gethostname(),
    "pid": os.getpid(),
    "cwd": str(ROOT),
    "python_executable": sys.executable,
    "python_version": platform.python_version(),
}
print("Example root:", ROOT)
print(json.dumps(host_evidence, indent=2))
""",
        tags=["safe-check"],
    ),
    code(
        """
from openshell_contained_workshop.host import load_env_file

loaded_names = load_env_file(ROOT / ".env")
os.environ.setdefault("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
print(f"Loaded {len(loaded_names)} configured names from .env. Values are hidden.")
"""
    ),
    markdown(
        "## 1. Preflight\n\n"
        "Check local tooling, the gateway, packages, files, and configuration presence. "
        "Only variable names and set/unset status are reported; secret values stay hidden."
    ),
    code(
        """
preflight = subprocess.run(
    [sys.executable, "scripts/check_env.py"],
    text=True,
    capture_output=True,
    check=False,
)
print(preflight.stdout)
if preflight.stderr:
    print(preflight.stderr)
if preflight.returncode != 0:
    raise RuntimeError("Preflight failed. Fix the reported prerequisites before continuing.")
"""
    ),
    markdown(
        "### Inspect The Shared Incident Fixture\n\n"
        "The first records establish a healthy baseline before inventory timeouts begin. "
        "Later, compare the agent summary with the deterministic counts in the generated JSON."
    ),
    code(
        """
log_path = ROOT / "workshop/data/sample_app.log"
log_lines = log_path.read_text(encoding="utf-8").splitlines()
print(f"Fixture records: {len(log_lines)}")
print("\\n".join(log_lines[:8]))
"""
    ),
    markdown(
        """
## 2. Build The Contained Runtime

OpenShell builds this folder's Dockerfile, applies the contained runtime policy,
and starts the sandbox. If the named sandbox already exists, the cell reuses it
and refreshes the dynamic policy. Delete and recreate it after changing baked
source or dependencies.

**Success check:** the sandbox reports `created` or `reused`. A reused sandbox
keeps earlier `/sandbox` artifacts, but each agent invocation still gets its own trace.
"""
    ),
    code(
        """
from openshell_contained_workshop.host import (
    DEFAULT_SANDBOX_NAME,
    open_session,
    prepare_sandbox,
)

sandbox_name = os.environ.get("OPENSHELL_SANDBOX_NAME", DEFAULT_SANDBOX_NAME)
sandbox_state = prepare_sandbox(example_root=ROOT, sandbox_name=sandbox_name)
client, session = open_session(sandbox_name)
print(f"Sandbox {sandbox_name!r} is ready ({sandbox_state}).")
"""
    ),
    markdown(
        "### Compare Host And Sandbox Processes\n\n"
        "This probe proves that OpenShell has a different hostname, Python executable, "
        "and process namespace. Lab 1 repeats the proof through an actual parent-to-subagent run."
    ),
    code(
        """
probe_source = (
    "import json, os, platform, socket, sys\\n"
    "print(json.dumps({\\n"
    "    'execution_boundary': os.environ.get('OPENSHELL_EXECUTION_BOUNDARY'),\\n"
    "    'hostname': socket.gethostname(),\\n"
    "    'pid': os.getpid(),\\n"
    "    'cwd': os.getcwd(),\\n"
    "    'python_executable': sys.executable,\\n"
    "    'python_version': platform.python_version(),\\n"
    "}))"
)

probe = session.exec(
    ["/app/.venv/bin/python", "-"],
    workdir="/app",
    env={"OPENSHELL_EXECUTION_BOUNDARY": "openshell-contained"},
    stdin=probe_source.encode("utf-8"),
    timeout_seconds=60,
)
if probe.exit_code != 0:
    raise RuntimeError("Sandbox runtime probe failed.")
sandbox_evidence = json.loads(probe.stdout)
print("HOST")
print(json.dumps(host_evidence, indent=2))
print("\\nOPENSHELL SANDBOX")
print(json.dumps(sandbox_evidence, indent=2))
assert sandbox_evidence["execution_boundary"] == "openshell-contained"
assert sandbox_evidence["hostname"] != host_evidence["hostname"]
"""
    ),
    markdown(
        """
## 3. Invocation Helper

The helper sends a non-secret JSON request on stdin. Credentials are injected
separately through an SDK environment map and are never placed in commands or
result files. It stores each structured result and trace URL by lab name so Lab 6
can present direct links without making you search earlier cell output.

The decisive boundary transition is:

```text
Host notebook
  -> OpenShell session.exec(/app/.venv/bin/python -m openshell_contained_workshop.runner)
     -> runner.build_agent()
        -> create_deep_agent(parent + subagents + tools)
           -> agent.invoke()
```

Everything after `session.exec(...)` runs inside OpenShell. Hosted NVIDIA NIM
inference and the LangSmith service remain external network services; their
clients run inside the sandbox.
"""
    ),
    code(
        """
from openshell_contained_workshop.host import invoke_contained_agent


def render_markdown(text: str) -> None:
    try:
        from IPython.display import Markdown, display
        display(Markdown(text))
    except Exception:
        print(text)


def trace_url(run_id: str, attempts: int = 8) -> str | None:
    flag = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"} or not os.environ.get("LANGSMITH_API_KEY"):
        return None
    from langsmith import Client
    langsmith_client = Client()
    for attempt in range(attempts):
        try:
            langsmith_client.flush(timeout=5)
            run = langsmith_client.read_run(uuid.UUID(run_id))
            return langsmith_client.get_run_url(
                run=run,
                project_name=os.environ.get("LANGSMITH_PROJECT") or None,
            )
        except Exception:
            if attempt + 1 == attempts:
                return None
            time.sleep(0.75)
    return None


lab_results: dict[str, dict] = {}
lab_trace_urls: dict[str, str | None] = {}


def read_sandbox_json(path: str) -> dict:
    readback = session.exec(["cat", path], timeout_seconds=60)
    if readback.exit_code != 0:
        raise RuntimeError(f"Could not read sandbox JSON artifact: {path}")
    return json.loads(readback.stdout)


def run_lab(prompt: str, *, lab: str, render_response: bool = True) -> dict:
    result = invoke_contained_agent(
        session,
        prompt=prompt,
        lab=lab,
        sandbox_name=sandbox_name,
    )
    lab_results[lab] = result
    if result["status"] == "ok" and render_response:
        render_markdown(result["final_text"])
    elif result["status"] != "ok":
        print("Contained run error:", result["error"])
    print("\\nRuntime evidence:")
    print(json.dumps(result["runtime"], indent=2))
    print("Artifacts created by this lab:", result.get("artifacts", []))
    url = trace_url(result["run_id"])
    lab_trace_urls[lab] = url
    print("LangSmith trace:", url or f"run id {result['run_id']}")
    return result
"""
    ),
    markdown(
        """
## Lab 1: Prove The Agent Runtime Boundary

**Goal:** prove that the parent agent delegates to a subagent whose tools and
subprocesses already run inside OpenShell. Look for the sandbox hostname,
`/app/.venv/bin/python`, PID namespace evidence, and `execution_boundary` marker.
"""
    ),
    code(
        """
runtime_result = run_lab(
    "Delegate to the incident-analyst subagent. Have it call inspect_runtime_boundary "
    "and run_contained_smoke_test. Explain the evidence that the parent, subagent tools, "
    "Python executable, and shell commands are inside OpenShell. Do not create another sandbox.",
    lab="runtime-boundary",
)
"""
    ),
    markdown(
        """
## Lab 2: Contained Incident Analysis

**Goal:** turn the shared log into reproducible evidence and two `/sandbox`
artifacts. Use the JSON as the source of truth: the fixture has 37 records,
12 `level=ERROR` records, and 15 HTTP 503 responses. Those counts are related but
not interchangeable. Treat root cause and customer impact as evidence-backed
interpretations; a severity label needs an organization-specific rubric.
"""
    ),
    code(
        """
incident_result = run_lab(
    "Delegate to the incident-analyst subagent and use analyze_incident_log. Summarize "
    "only the exact evidence in the generated artifacts, the suspected cause, artifact paths, "
    "and proof that analysis executed inside the same OpenShell runtime as the agent. Keep "
    "level=ERROR and HTTP 5xx counts separate. Do not assign severity, claim that all failures "
    "have one message, or invent endpoint details.",
    lab="incident-analysis",
    render_response=False,
)

incident_summary = read_sandbox_json("/sandbox/incident_summary.json")
assert incident_summary["total_records"] == 37
assert incident_summary["level_counts"] == {"INFO": 19, "WARN": 6, "ERROR": 12}
assert incident_summary["level_error_count"] == 12
assert incident_summary["http_5xx_count"] == 15
assert incident_summary["status_counts"] == {"200": 22, "503": 15}
assert incident_summary["top_failing_endpoints"][:3] == [
    ["/api/inventory", 6],
    ["/api/checkout", 6],
    ["/checkout", 3],
]

render_markdown(
    f'''
### Artifact-backed incident checkpoint

- **37 records:** 19 INFO, 6 WARN, and 12 `level=ERROR`
- **15 HTTP 5xx responses:** 6 `/api/inventory`, 6 `/api/checkout`, and 3 `/checkout`
- **Failure window:** `{incident_summary['first_failure_timestamp']}` through
  `{incident_summary['last_failure_timestamp']}`
- **Supported hypothesis:** {incident_summary['suspected_cause']}
- **Artifacts:** `/sandbox/incident_summary.json` and `/sandbox/incident_report.md`
- **Runtime:** `{incident_result['runtime']['execution_boundary']}` in
  `{incident_result['runtime']['sandbox_name']}`

The model response remains in the LangSmith trace for inspection. This notebook
uses the generated artifact as the source of truth and does not assert a severity,
a complete outage, or one identical cause message for every 5xx response.
'''
)
"""
    ),
    markdown(
        "### Inspect Artifacts Directly Through OpenShell\n\n"
        "This host-side SDK readback is independent of the model's prose. Confirm the "
        "counts, timeline, suspected cause, and artifact paths before accepting the summary."
    ),
    code(
        """
artifact_commands = [
    ["ls", "-lah", "/sandbox"],
    ["python3", "-m", "json.tool", "/sandbox/incident_summary.json"],
    ["sed", "-n", "1,100p", "/sandbox/incident_report.md"],
]
for command in artifact_commands:
    print("\\n$", " ".join(command))
    result = session.exec(command, timeout_seconds=120)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.exit_code != 0:
        raise RuntimeError(f"Artifact inspection failed: {command}")
"""
    ),
    markdown(
        """
## Lab 3: Generic Deep Agents Execution

**Goal:** contrast the purpose-built incident tool with normal Deep Agents
`write_file`, `execute`, and `read_file` tools. The generated program and its
Python subprocess still share the same outer OpenShell boundary as the agent.
"""
    ),
    code(
        """
generic_result = run_lab(
    "Use the normal Deep Agents write_file, execute, and read_file tools rather than the "
    "analyze_incident_log tool. Create /sandbox/generic_contained_demo.py that prints compact "
    "JSON with hostname, pid, cwd, python_version, count_1_to_25, and sum_1_to_25. Execute it, "
    "read it back, and explain only the observed shared sandbox identity. Do not name "
    "undocumented runtime mechanisms such as gVisor, runsc, seccomp, or cgroups.",
    lab="generic-execution",
    render_response=False,
)

generic_probe = session.exec(
    ["python3", "/sandbox/generic_contained_demo.py"],
    workdir="/sandbox",
    timeout_seconds=60,
)
if generic_probe.exit_code != 0:
    raise RuntimeError("Could not verify the generic Deep Agents artifact.")
generic_evidence = json.loads(generic_probe.stdout)
assert generic_evidence["hostname"] == generic_result["runtime"]["hostname"]
assert generic_evidence["cwd"] == "/sandbox"
assert generic_evidence["count_1_to_25"] == list(range(1, 26))
assert generic_evidence["sum_1_to_25"] == 325

render_markdown(
    f'''
### Verified generic execution checkpoint

```json
{json.dumps(generic_evidence, indent=2)}
```

The agent runner and verified child process report the same sandbox hostname
`{generic_evidence['hostname']}`. The runner uses `/app/.venv/bin/python`; the
generated program executes from `/sandbox`. Both are inside the outer OpenShell
filesystem and process boundary. Lab 3's trace is the evidence that the agent used
`write_file`, `execute`, and `read_file`; this checkpoint deliberately avoids
claiming undocumented low-level runtime mechanisms.
'''
)
"""
    ),
    markdown(
        """
## Lab 4: Policy Enforcement From Inside The Agent

**Goal:** separate ordinary Unix permissions from OpenShell policy enforcement.
The process runs as UID 1000 (`sandbox`), and `/home/sandbox` is owned by that user
and normally writable. OpenShell marks it read-only, while `/sandbox` remains
writable. The two command spans should therefore show one success and one expected denial.

If older saved output mentions a root process or an `/etc` write, rerun this lab;
that explanation did not prove the OpenShell boundary.
"""
    ),
    code(
        """
policy_result = run_lab(
    "Delegate to the policy-analyst subagent and use run_policy_boundary_demo. Explain why the "
    "/sandbox write succeeds, why the user-owned /home/sandbox write is expected to fail, and "
    "which contained execute spans prove enforcement. Cite the emitted UID, directory owner, "
    "and mode. Never claim the runtime user is root. Do not bypass or weaken the policy.",
    lab="policy-enforcement",
)
"""
    ),
    markdown(
        """
## Lab 5: Skills Inside The Runtime

**Goal:** connect on-demand skill instructions to orchestration behavior. The
host prints the source for study, while the contained agent loads its baked copy
from `/app/skills`. The observability coach explains what to verify; Lab 6 is
where you confirm the actual hierarchy rather than treating that explanation as proof.
"""
    ),
    code(
        """
skill_path = ROOT / "skills/incident-log-analysis/SKILL.md"
print(skill_path.read_text(encoding="utf-8")[:1800])

skills_result = run_lab(
    "Delegate to the observability-coach subagent. Review the incident-log-analysis and "
    "langsmith-observability skills, then return a checklist of questions for inspecting "
    "skills, parent orchestration, subagent delegation, and command execution in LangSmith. "
    "You do not have trace access: do not claim to have inspected a trace, do not invent "
    "dedicated skill spans or tags, and label everything except openshell.contained.execute "
    "as something the participant must verify.",
    lab="skills-and-observability",
    render_response=False,
)

render_markdown(
    '''
### Skills and trace-reading contract

- The parent and each named subagent are configured with the baked `/skills/` directory.
- This run asks the parent to delegate to the observability coach; confirm the actual
  `task` handoff in its LangSmith trace.
- The coach has no LangSmith-reading tool. Its response is a proposed inspection
  checklist, not proof of span names, tags, metadata inheritance, or child fields.
- `openshell.contained.execute` is guaranteed because the contained backend creates
  that custom span explicitly. Record every other trace detail exactly as observed.

The coach's full response is retained in the trace so you can compare its claims
with the trace itself in Lab 6.
'''
)
"""
    ),
    markdown(
        """
## Lab 6: Debugging With LangSmith

Each lab is a separate root run. The next cell puts all trace links here at the
top of the lab, then maps each inspection task to the trace that contains the
relevant evidence. You do not need to search previous output cells.
"""
    ),
    code(
        """
trace_guide = [
    ("Lab 1", "runtime-boundary", "Parent → incident analyst → contained smoke test"),
    ("Lab 2", "incident-analysis", "Analysis tool, command spans, and artifact creation"),
    ("Lab 3", "generic-execution", "Built-in write_file → execute → read_file flow"),
    ("Lab 4", "policy-enforcement", "Allowed and denied command exit codes"),
    ("Lab 5", "skills-and-observability", "Skill-guided observability handoff"),
]

rows = [
    "### Open the traces",
    "",
    "| Run | Trace | Start with |",
    "|---|---|---|",
]
for label, lab, focus in trace_guide:
    result = lab_results[lab]
    url = lab_trace_urls.get(lab) or trace_url(result["run_id"])
    lab_trace_urls[lab] = url
    trace_link = f"[Open trace]({url})" if url else f"Run ID `{result['run_id']}`"
    rows.append(f"| {label} | {trace_link} | {focus} |")
render_markdown("\\n".join(rows))

checklist = [
    "Start with Lab 2 and confirm execution_boundary=openshell-contained on the root run.",
    "Expand the task handoff from the parent to the incident-analyst subagent.",
    "Inspect openshell.contained.execute spans and compare their exit codes and output previews.",
    "Open Lab 4 and verify UID 1000 owns /home/sandbox before the policy-denied write.",
    "Compare host evidence with the runtime evidence stored in each structured result.",
    "Confirm each lab reports only the artifacts it created and that they stay under /sandbox.",
    "For Lab 5, record the observed skill-related spans or tags; "
    "do not assume dedicated ones exist.",
    "Treat model prose as a claim and artifacts plus observed trace fields as evidence.",
]
print("\\nTrace inspection checklist")
for index, item in enumerate(checklist, start=1):
    print(f"{index}. {item}")
"""
    ),
    markdown(
        """
## Wrap-Up

The notebook was only the host control plane. The model client, parent Deep Agent,
subagents, Deep Agents tools, generated Python, shell commands, skills, and
artifacts all lived inside OpenShell. Hosted NVIDIA NIM inference and LangSmith
remained external services reached through policy-controlled network endpoints.
The runtime boundary now protects the agent process as well as its child execution.
"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
print(f"wrote {OUTPUT}")
