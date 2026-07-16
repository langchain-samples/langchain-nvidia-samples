# NVIDIA OpenShell Contained Deep Agent Workshop

This notebook-first workshop puts the **agent runtime itself** inside NVIDIA OpenShell. The parent Deep Agent orchestrator, specialized subagents, model client, tool calls, generated Python, and artifacts all execute in one policy-governed sandbox. The local Jupyter notebook only provisions that sandbox, sends requests, and displays results.

This is a companion to [`nemotron-openshell-incident-agent`](../nemotron-openshell-incident-agent). It deliberately reuses the same incident log so the runtime-boundary difference is easy to see.

## Architecture

```mermaid
flowchart LR
    Participant[Participant] --> Notebook[Thin host notebook]
    Notebook -->|create / invoke / read results| OpenShell[OpenShell sandbox]
    subgraph OpenShell
        Runner[Contained runner]
        Parent[Parent Deep Agent]
        Incident[Incident analyst]
        Observability[Observability coach]
        Policy[Policy analyst]
        Python[Generated Python and shell]
        Artifacts[/sandbox artifacts]
        Runner --> Parent
        Parent --> Incident
        Parent --> Observability
        Parent --> Policy
        Incident --> Python
        Python --> Artifacts
    end
    Parent -->|NVIDIA NIM| Nemotron[Nemotron Ultra]
    Parent -->|traces| LangSmith[LangSmith]
```

The notebook never imports `openshell_contained_workshop.agent`. The sandbox runner is the only component that constructs the parent agent.

The workbook treats model prose as a claim and generated artifacts plus observed
trace fields as evidence. Incident and generic-execution labs therefore render
deterministic checkpoints while retaining the complete agent response in LangSmith.

## Contents

- `workshop/notebooks/participant_walkthrough.ipynb` — primary workshop workbook.
- `workshop/data/sample_app.log` — synthetic incident fixture shared with the companion example.
- `workshop/policies/contained-runtime.yaml` — filesystem, process, and network policy.
- `src/openshell_contained_workshop/` — host launcher and sandbox-resident Deep Agent app.
- `skills/` — incident, policy, and observability instructions baked into the runtime.
- `scripts/check_env.py` — secret-safe local preflight.
- `scripts/check_notebook.py` — notebook structure and syntax validation.
- `tests/` — unit, architecture, packaging, and safety regression tests.

## What You Will Learn

1. Build a locked Python runtime image for OpenShell.
2. Prove that the parent agent and its executable share the sandbox boundary.
3. Delegate incident analysis to a subagent inside that boundary.
4. Generate and inspect `/sandbox/incident_summary.json` and `/sandbox/incident_report.md`.
5. Compare an allowed `/sandbox` write with a policy-denied write to the
   user-owned `/home/sandbox` directory.
6. Open direct per-lab links to trace parent, subagent, tool, command, and policy
   activity in LangSmith.

## Requirements

- Python 3.12+
- `uv` and [Socket Firewall Free (`sfw`)](https://github.com/SocketDev/sfw-free)
- Docker Desktop or another Docker-compatible local runtime
- OpenShell 0.0.51 with a reachable gateway
- NVIDIA API key for hosted Nemotron through NIM, or a self-hosted NIM endpoint
- LangSmith API key for tracing

## Local OpenShell Gateway Requirement

This example installs the OpenShell client, but it does not start a gateway for
you. A complete local setup has three layers:

1. This Python project and its thin host notebook.
2. The OpenShell CLI used by the host launcher.
3. A selected, reachable OpenShell gateway that can build and run Docker-backed sandboxes.

Docker can be healthy while OpenShell still reports `No gateway configured` or
`Connection refused`. Confirm the selected gateway before opening the notebook:

```bash
uv run openshell status
```

## Quickstart

```bash
cd examples/nemotron-openshell-contained-incident-agent
cp .env.example .env
```

Fill in `NVIDIA_API_KEY` and `LANGSMITH_API_KEY`, then install the locked environment:

Install [Socket Firewall Free (`sfw`)](https://github.com/SocketDev/sfw-free)
using its official instructions if `command -v sfw` returns nothing. Then run:

```bash
command -v sfw
sfw uv sync --extra notebook --extra dev
```

Configure and select an OpenShell gateway before starting the notebook. For a package-managed local gateway this is commonly:

```bash
uv run openshell gateway add https://127.0.0.1:17670 --local --name openshell
uv run openshell gateway select openshell
```

If that gateway already exists, select it without adding it again. Confirm readiness with `uv run openshell status`.

If the package-managed gateway has not started or its mTLS bundle is missing,
restart the service before registering it. On macOS with Homebrew this is commonly:

```bash
which openshell
brew services restart openshell
uv run openshell status
uv run openshell gateway add https://127.0.0.1:17670 --local --name openshell
uv run openshell gateway select openshell
```

Alternatively, follow the NVIDIA OpenShell installation documentation to start
or connect to another local gateway, then select it with `openshell gateway select`.

Run the complete preflight after the gateway is selected:

```bash
uv run python scripts/check_env.py
```

Start the workshop:

```bash
uv run jupyter lab workshop/notebooks/participant_walkthrough.ipynb
```

The notebook creates `contained-agent-workshop` from this folder's Dockerfile. If it already exists, the notebook reuses it and refreshes the dynamic policy. Delete and recreate the sandbox after changing the Dockerfile, lockfile, source, skills, or baked workshop data.

The first run builds the custom image and can take several minutes. To force a
clean rebuild after source or image changes:

```bash
uv run openshell sandbox delete contained-agent-workshop
```

Then restart the notebook kernel and run all cells.

## Troubleshooting

- **`No gateway configured` or `Connection refused`:** run `uv run openshell
  status`, start the gateway service, and select the correct gateway.
- **`mTLS certificates ... were not found`:** the package-managed gateway has
  not started or has not provisioned its client certificate bundle yet.
- **Sandbox is in `Phase: Error`:** delete `contained-agent-workshop`, then rerun
  the build cell so OpenShell creates a fresh image.
- **Changes under `src/`, `skills/`, `workshop/`, or `Dockerfile` do not appear:**
  delete and rebuild the sandbox because those files are baked into the image.
- **Hosted NIM returns `503 ResourceExhausted`:** this is upstream capacity
  pressure, not an OpenShell failure. Wait briefly and rerun only the failed lab.
- **Using `NVIDIA_BASE_URL`:** add that endpoint to
  `workshop/policies/contained-runtime.yaml` before rebuilding the sandbox.

## Runtime and Secret Boundaries

- `/app` contains the locked environment, source, skills, and fixture and is read-only at runtime.
- `/sandbox` and `/tmp` are writable.
- The default policy permits the contained Python executable to reach hosted NVIDIA NIM and LangSmith over HTTPS.
- `.env` is excluded from the image. The host launcher injects only an explicit environment-variable allowlist into the runner process through the OpenShell SDK.
- Secret values are never placed in command arguments, result files, trace metadata, or notebook output.
- A self-hosted `NVIDIA_BASE_URL` needs a matching endpoint in `workshop/policies/contained-runtime.yaml` before the sandbox can reach it.

## Repository Layout

- `workshop/notebooks/participant_walkthrough.ipynb` — participant workbook
- `workshop/data/sample_app.log` — deterministic synthetic incident fixture
- `src/openshell_contained_workshop/host.py` — thin host launcher
- `src/openshell_contained_workshop/runner.py` — sandbox-resident JSON runner
- `src/openshell_contained_workshop/backend.py` — local execution backend inside OpenShell
- `src/openshell_contained_workshop/agent.py` — parent and subagent configuration
- `workshop/policies/contained-runtime.yaml` — filesystem, process, and network boundary
- `scripts/build_notebook.py` — canonical notebook-source generator
- `scripts/check_env.py` and `scripts/check_notebook.py` — participant preflight and validation
- `tests/` — unit and architecture regression suite
- `Dockerfile` and `uv.lock` — locked runtime image

## Validation

```bash
uv run pytest
uv run ruff check .
uv run python scripts/check_notebook.py
sfw uv lock --check
```

The live notebook labs require a configured gateway and credentials. Unit and notebook-structure tests do not make model calls.
