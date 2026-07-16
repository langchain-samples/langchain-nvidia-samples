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
        Artifacts["/sandbox artifacts"]
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
- `uv`
- Docker Desktop or another Docker-compatible local runtime
- A local OpenShell runtime with a reachable gateway (the project locks the client to 0.0.51)
- NVIDIA API key for hosted Nemotron through NIM, or a self-hosted NIM endpoint
- LangSmith API key for tracing

## End-to-End Quickstart

### 1. Configure the project

```bash
cd examples/nemotron-openshell-contained-incident-agent
cp .env.example .env
```

Fill in `NVIDIA_API_KEY` and `LANGSMITH_API_KEY`. For hosted NVIDIA NIM, leave
`NVIDIA_BASE_URL` empty; set it only when using a self-hosted NIM endpoint. Then
install the locked environment. This installs the OpenShell 0.0.51 Python client
used by the notebook:

```bash
uv sync --extra notebook --extra dev
```

No separate Socket Firewall installation is required on the participant machine.

### 2. Install and start an OpenShell gateway

The Python client does not install or start the separate gateway service that
builds and runs sandboxes. A complete setup has three layers:

1. This Python project and its thin host notebook.
2. The OpenShell CLI used by the host launcher.
3. A selected, reachable OpenShell gateway that can build and run Docker-backed sandboxes.

Docker can be healthy while OpenShell still reports `No gateway configured` or
`Connection refused`. Choose one of the following gateway paths.

#### Option A: NVIDIA local installation (recommended)

Follow the [NVIDIA OpenShell quickstart](https://docs.nvidia.com/openshell/latest/get-started/quickstart)
for your operating system. Pin the installer to the same version as this
workshop's Python client:

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh \
  | OPENSHELL_VERSION=v0.0.51 sh
```

After installation, confirm that the host-level installation and its gateway
service are available:

```bash
which openshell
openshell status
```

For a package-managed local gateway listening on the standard loopback endpoint,
register and select it for the project client:

```bash
uv run openshell gateway add https://127.0.0.1:17670 --local --name openshell
uv run openshell gateway select openshell
uv run openshell status
```

If `gateway add` says the gateway already exists, skip that command and select
it. If the service or its mTLS bundle is not ready, restart the package-managed
service before registering it. On macOS with Homebrew this is commonly:

```bash
brew services restart openshell
uv run openshell gateway select openshell
uv run openshell status
```

#### Option B: loopback-only container gateway

For local development, you can run the same pinned gateway used by the companion
workshop. This disables TLS and binds the gateway only to `127.0.0.1`; do not use
this configuration for a shared or remote gateway.

```bash
docker run -d \
  --name openshell-gateway \
  --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v openshell-state:/var/openshell \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e OPENSHELL_DRIVERS=docker \
  -e OPENSHELL_DB_URL=sqlite:/var/openshell/openshell.db \
  -e OPENSHELL_DISABLE_TLS=true \
  ghcr.io/nvidia/openshell/gateway@sha256:5e251baec790a61242a2190ea6fe26366d4dfe15ba1a7a0b612b5bef5af19aaa

uv run openshell gateway add http://127.0.0.1:8080 --local --name local
uv run openshell gateway select local
uv run openshell status
```

Whichever path you use, do not continue until `uv run openshell status` shows a
selected gateway without a connection error.

### 3. Verify the environment and run the workshop

Run the complete preflight:

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
uv lock --check
```

The live notebook labs require a configured gateway and credentials. Unit and notebook-structure tests do not make model calls.
