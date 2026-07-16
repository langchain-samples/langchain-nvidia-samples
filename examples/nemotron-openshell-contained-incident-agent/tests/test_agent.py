from __future__ import annotations

import unittest

from openshell_contained_workshop.agent import build_agent_config
from openshell_contained_workshop.prompts import (
    OBSERVABILITY_COACH_PROMPT,
    ORCHESTRATOR_PROMPT,
)


class AgentConfigurationTests(unittest.TestCase):
    def test_prompts_reject_unsupported_runtime_and_trace_claims(self) -> None:
        self.assertIn("Never assign an incident severity", ORCHESTRATOR_PROMPT)
        self.assertIn("gVisor", ORCHESTRATOR_PROMPT)
        self.assertIn("do not have a LangSmith trace-reading tool", OBSERVABILITY_COACH_PROMPT)
        self.assertIn("Do not invent dedicated", OBSERVABILITY_COACH_PROMPT)

    def test_parent_and_subagents_share_contained_backend(self) -> None:
        model = object()
        backend = object()

        config = build_agent_config(model=model, backend=backend)

        self.assertIs(config["model"], model)
        self.assertIs(config["backend"], backend)
        self.assertEqual(
            [subagent["name"] for subagent in config["subagents"]],
            ["incident-analyst", "observability-coach", "policy-analyst"],
        )
        self.assertTrue(all(subagent["skills"] == ["/skills/"] for subagent in config["subagents"]))
        self.assertIn("already running", config["system_prompt"])
        self.assertIn("Do not create", config["system_prompt"])


if __name__ == "__main__":
    unittest.main()
