---
name: langsmith-observability
description: Interpret traces from a parent Deep Agent and subagents running inside OpenShell.
---

# LangSmith Observability

Use this skill when the participant asks how to inspect or debug a contained run.

## Trace Reading Checklist

- Start at the root parent-agent run and confirm `execution_boundary=openshell-contained`.
- Identify `task` handoffs to the incident analyst, observability coach, or policy analyst.
- Inspect model calls for latency, token use, and errors.
- Inspect `openshell.contained.execute` spans for commands, exit codes, and bounded output previews.
- Compare the runtime evidence in the result with the host notebook's hostname and PID.
- Confirm generated artifact paths stay under `/sandbox`.
- Treat the denied `/home/sandbox` write as expected policy evidence, not a failure to hide.
- Never copy secret values from a trace.
