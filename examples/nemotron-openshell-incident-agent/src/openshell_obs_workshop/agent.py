"""Deep Agent entrypoint used by the workshop notebook."""

from __future__ import annotations

from datetime import date

from deepagents import create_deep_agent

from .backend import create_backend
from .models import build_chat_model
from .prompts import (
    OBSERVABILITY_COACH_PROMPT,
    ORCHESTRATOR_PROMPT,
    POLICY_ANALYST_PROMPT,
    SANDBOX_ENGINEER_PROMPT,
)
from .tools import analyze_incident_log, run_policy_boundary_demo, run_sandbox_smoke_test

_today = date.today().isoformat()
_model = build_chat_model()


_sandbox_engineer = {
    "name": "sandbox-engineer",
    "description": (
        "Use for OpenShell command execution, Python scripts, file roundtrips, "
        "environment checks, and sandbox debugging."
    ),
    "system_prompt": SANDBOX_ENGINEER_PROMPT,
    "model": _model,
    "tools": [analyze_incident_log, run_sandbox_smoke_test],
    "skills": ["/skills/"],
}

_observability_coach = {
    "name": "observability-coach",
    "description": (
        "Use for LangSmith trace interpretation, debugging guidance, metadata/tagging "
        "recommendations, and run comparison."
    ),
    "system_prompt": OBSERVABILITY_COACH_PROMPT,
    "model": _model,
    "tools": [],
    "skills": ["/skills/"],
}

_policy_analyst = {
    "name": "policy-analyst",
    "description": (
        "Use for safe OpenShell policy-boundary demos, denied operation analysis, "
        "and policy observability explanations."
    ),
    "system_prompt": POLICY_ANALYST_PROMPT,
    "model": _model,
    "tools": [run_policy_boundary_demo],
    "skills": ["/skills/"],
}

_agent_kwargs = {
    "name": "openshell-observability-workshop",
    "model": _model,
    "tools": [analyze_incident_log, run_policy_boundary_demo, run_sandbox_smoke_test],
    "system_prompt": ORCHESTRATOR_PROMPT.format(date=_today),
    "subagents": [_sandbox_engineer, _observability_coach, _policy_analyst],
    "skills": ["/skills/"],
    "backend": create_backend(None),
}

agent = create_deep_agent(**_agent_kwargs)
