---
name: langsmith-observability
description: Use for interpreting LangSmith traces, adding useful metadata, and comparing agent runs.
---

# LangSmith Observability

Use this skill when the participant asks how to inspect, debug, or improve a run.

## Trace Reading Checklist

- Start at the root run and read the user input.
- Identify subagent handoffs.
- Inspect model calls for prompt shape, token usage, and latency.
- Inspect tool calls for command inputs, exit codes, output previews, and errors.
- Look for policy denials or command failures before changing prompts.
- Compare traces before and after skill or prompt edits.

## Useful Tags

- `workshop`
- `smoke-test`
- `sandbox-exec`
- `policy-demo`
- `skill-iteration`
- `debugging`

## Useful Metadata

- `lab`
- `participant_group`
- `sandbox_name`
- `scenario`
- `expected_failure`

