---
name: openshell-policy
description: Use for safe OpenShell policy-boundary demos and denied-operation analysis.
---

# OpenShell Policy

Use this skill when the participant asks to demonstrate sandbox boundaries, network restrictions, filesystem restrictions, or policy enforcement.

## Instructions

- Do not bypass policies.
- Use harmless, deterministic test commands.
- Treat a blocked action as a valid workshop result.
- Explain whether the failure came from the model, shell command, sandbox runtime, or OpenShell policy.
- Point the participant to the OpenShell command span and error output in LangSmith.
- Avoid commands that could reveal local host data or secrets.

## Safe Demo Prompt Pattern

Ask the agent to attempt one blocked action, stop, and explain the failure. Do not ask it to find another route around the block.

For the workshop fixture, writing under `/sandbox` should be allowed and writing under protected system paths such as `/etc` should be denied unless the instructor changes the policy.
