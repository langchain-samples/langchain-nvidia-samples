"""Lazy construction of the Deep Agent that lives inside OpenShell."""

from __future__ import annotations

from datetime import date
from typing import Any

from deepagents import create_deep_agent

from .backend import create_backend
from .models import build_chat_model
from .prompts import (
    INCIDENT_ANALYST_PROMPT,
    OBSERVABILITY_COACH_PROMPT,
    ORCHESTRATOR_PROMPT,
    POLICY_ANALYST_PROMPT,
)
from .tools import (
    analyze_incident_log,
    inspect_runtime_boundary,
    run_contained_smoke_test,
    run_policy_boundary_demo,
)


def build_agent_config(*, model: Any | None = None, backend: Any | None = None) -> dict[str, Any]:
    """Return the complete contained-runtime Deep Agent configuration."""

    chat_model = model or build_chat_model()
    contained_backend = backend or create_backend(None)
    incident_analyst = {
        "name": "incident-analyst",
        "description": (
            "Analyze logs, execute Python, verify the contained runtime, "
            "and produce incident artifacts."
        ),
        "system_prompt": INCIDENT_ANALYST_PROMPT,
        "model": chat_model,
        "tools": [inspect_runtime_boundary, analyze_incident_log, run_contained_smoke_test],
        "skills": ["/skills/"],
    }
    observability_coach = {
        "name": "observability-coach",
        "description": "Interpret LangSmith traces for the contained parent agent and subagents.",
        "system_prompt": OBSERVABILITY_COACH_PROMPT,
        "model": chat_model,
        "tools": [inspect_runtime_boundary],
        "skills": ["/skills/"],
    }
    policy_analyst = {
        "name": "policy-analyst",
        "description": "Run and explain safe OpenShell policy-boundary demonstrations.",
        "system_prompt": POLICY_ANALYST_PROMPT,
        "model": chat_model,
        "tools": [inspect_runtime_boundary, run_policy_boundary_demo],
        "skills": ["/skills/"],
    }
    return {
        "name": "openshell-contained-incident-agent",
        "model": chat_model,
        "tools": [
            inspect_runtime_boundary,
            run_contained_smoke_test,
            analyze_incident_log,
            run_policy_boundary_demo,
        ],
        "system_prompt": ORCHESTRATOR_PROMPT.format(date=date.today().isoformat()),
        "subagents": [incident_analyst, observability_coach, policy_analyst],
        "skills": ["/skills/"],
        "backend": contained_backend,
    }


def build_agent():
    """Create the parent Deep Agent inside the current OpenShell process."""

    return create_deep_agent(**build_agent_config())
