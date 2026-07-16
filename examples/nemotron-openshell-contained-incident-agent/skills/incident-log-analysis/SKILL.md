---
name: incident-log-analysis
description: Analyze the workshop application log from inside OpenShell and produce incident artifacts.
---

# Incident Log Analysis

Use this skill for incident summaries, error spikes, latency patterns, and remediation recommendations.

## Instructions

- Remember that the parent agent, subagent, Python process, and filesystem tools already run inside OpenShell.
- Treat `/workshop/data/sample_app.log` as the virtual source fixture, backed by `/app/workshop/data/sample_app.log`.
- Copy source data into `/sandbox` before analysis.
- Write Python scripts and generated files under `/sandbox`.
- Parse records before summarizing and compute counts by level, service, status, failing endpoint, slow requests, p95 latency, and first/last errors.
- Keep `level=ERROR` counts separate from HTTP 5xx counts, and do not assign an
  incident severity unless the participant provides a severity rubric.
- Write `/sandbox/incident_summary.json` and `/sandbox/incident_report.md`.
- Read the artifacts back before reporting success.
- Do not create or call a nested sandbox and do not expose credentials.

## Report Shape

```markdown
# Incident Report

## Executive Summary
## Evidence
## Timeline
## Suspected Cause
## Recommended Next Actions
```
