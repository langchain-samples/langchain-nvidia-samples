---
name: openshell-policy
description: Demonstrate and explain the contained agent runtime's filesystem and network boundaries.
---

# OpenShell Policy

## Instructions

- Do not bypass or weaken policy controls.
- Use harmless, deterministic commands.
- `/app` is read-only source, while `/sandbox` and `/tmp` are writable.
- `/home/sandbox` is owned by the `sandbox` runtime user but is read-only under
  the OpenShell filesystem policy. Use it for the expected-denial demonstration
  so ordinary Unix ownership is not mistaken for the policy boundary.
- The default network policy permits the contained Python runtime to reach hosted NVIDIA NIM and LangSmith only.
- Treat a blocked operation as a valid workshop result.
- Explain whether a failure came from the model, a command, Unix permissions, or OpenShell enforcement.
- Never inspect host data or print credentials.
