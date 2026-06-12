---
name: incident-log-analysis
description: Use for analyzing application logs with Python inside the OpenShell sandbox and producing incident reports.
---

# Incident Log Analysis

Use this skill when the participant asks for application log analysis, incident summaries, error spikes, latency patterns, or remediation recommendations.

## Instructions

- Treat `/workshop/data/sample_app.log` as the canonical workshop log fixture.
- Copy source data into `/sandbox` before writing analysis scripts.
- Write Python scripts under `/sandbox`.
- Prefer the Python standard library: `collections`, `datetime`, `json`, `statistics`, and `re`.
- Parse logs into structured records before summarizing.
- Compute concrete evidence:
  - counts by level
  - counts by service
  - counts by status code
  - top failing endpoints
  - slowest requests
  - p95 latency by service when enough samples exist
  - first and last error timestamps
- Write two artifacts:
  - `/sandbox/incident_summary.json`
  - `/sandbox/incident_report.md`
- After writing artifacts, read them back or print a concise preview.
- Do not assume GPU libraries are available.

## Report Shape

```markdown
# Incident Report

## Executive Summary

## Evidence

## Timeline

## Suspected Cause

## Recommended Next Actions
```

