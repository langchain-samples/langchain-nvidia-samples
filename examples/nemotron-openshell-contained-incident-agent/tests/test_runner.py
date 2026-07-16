from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from openshell_contained_workshop.runner import LAB_ARTIFACTS, run_request, validate_request


def request() -> dict[str, str]:
    run_id = uuid.uuid4()
    return {
        "lab": "unit-test",
        "prompt": "Return a contained result.",
        "run_id": str(run_id),
        "thread_id": f"contained-unit-test-{run_id.hex[:8]}",
    }


class FakeAgent:
    def invoke(self, payload, config):  # type: ignore[no-untyped-def]
        self.payload = payload
        self.config = config
        return {"messages": [SimpleNamespace(content="contained result")]}


class FailingAgent:
    def invoke(self, payload, config):  # type: ignore[no-untyped-def]
        del payload, config
        raise RuntimeError("NVIDIA_API_KEY=placeholder")


class RunnerTests(unittest.TestCase):
    def test_artifacts_are_scoped_to_the_lab_that_created_them(self) -> None:
        self.assertEqual(
            [path.name for path in LAB_ARTIFACTS["incident-analysis"]],
            ["incident_summary.json", "incident_report.md"],
        )
        self.assertEqual(
            [path.name for path in LAB_ARTIFACTS["generic-execution"]],
            ["generic_contained_demo.py"],
        )
        self.assertEqual(
            [path.name for path in LAB_ARTIFACTS["policy-enforcement"]],
            ["policy_allowed.txt"],
        )

    def test_validate_request_rejects_invalid_lab(self) -> None:
        payload = request()
        payload["lab"] = "../escape"

        with self.assertRaisesRegex(ValueError, "lowercase slug"):
            validate_request(payload)

    def test_success_writes_structured_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, record = run_request(
                request(),
                agent_factory=FakeAgent,
                result_root=Path(directory),
            )

            self.assertTrue(path.exists())
            self.assertEqual(record["status"], "ok")
            self.assertEqual(record["final_text"], "contained result")
            self.assertEqual(record["runtime"]["execution_boundary"], "openshell-contained")

    def test_failure_is_serialized_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, record = run_request(
                request(),
                agent_factory=FailingAgent,
                result_root=Path(directory),
            )

            self.assertTrue(path.exists())
            self.assertEqual(record["status"], "error")
            self.assertIn("[REDACTED]", record["error"])
            self.assertNotIn("placeholder", record["error"])


if __name__ == "__main__":
    unittest.main()
