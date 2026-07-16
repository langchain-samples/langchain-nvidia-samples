from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openshell_contained_workshop.host import (
    invoke_contained_agent,
    load_env_file,
    prepare_sandbox,
    runtime_environment,
)


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.result_path = f"/sandbox/results/test-{uuid.uuid4()}.json"

    def exec(self, argv, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"argv": argv, **kwargs})
        if argv[0] == "cat":
            payload = {
                "status": "ok",
                "lab": "test",
                "run_id": str(uuid.uuid4()),
                "thread_id": "contained-test",
                "final_text": "inside",
                "runtime": {"execution_boundary": "openshell-contained"},
                "artifacts": [],
            }
            return SimpleNamespace(stdout=json.dumps(payload), stderr="", exit_code=0)
        return SimpleNamespace(
            stdout=f"RESULT_PATH={self.result_path}\n",
            stderr="",
            exit_code=0,
        )


class HostLauncherTests(unittest.TestCase):
    def test_load_env_file_returns_names_without_overwriting_existing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("NVIDIA_MODEL=test-model\nLANGSMITH_PROJECT=test-project\n")
            with patch.dict(os.environ, {"NVIDIA_MODEL": "existing"}, clear=False):
                loaded = load_env_file(path)

                self.assertEqual(os.environ["NVIDIA_MODEL"], "existing")
                self.assertIn("LANGSMITH_PROJECT", loaded)
                self.assertNotIn("NVIDIA_MODEL", loaded)

    def test_runtime_environment_is_allowlisted(self) -> None:
        source = {
            "NVIDIA_API_KEY": "placeholder-nvidia",
            "LANGSMITH_API_KEY": "placeholder-langsmith",
            "UNRELATED_VALUE": "must-not-cross",
        }

        environment = runtime_environment(sandbox_name="contained", source=source)

        self.assertEqual(environment["OPENSHELL_SANDBOX_NAME"], "contained")
        self.assertEqual(environment["OPENSHELL_EXECUTION_BOUNDARY"], "openshell-contained")
        self.assertNotIn("UNRELATED_VALUE", environment)

    def test_invoke_uses_stdin_and_reads_structured_result(self) -> None:
        session = FakeSession()

        result = invoke_contained_agent(
            session,  # type: ignore[arg-type]
            prompt="prove containment",
            lab="test",
            sandbox_name="contained",
        )

        runner_call = session.calls[0]
        self.assertEqual(
            runner_call["argv"],
            ["/app/.venv/bin/python", "-m", "openshell_contained_workshop.runner"],
        )
        self.assertIsInstance(runner_call["stdin"], bytes)
        self.assertNotIn("prove containment", " ".join(runner_call["argv"]))  # type: ignore[arg-type]
        self.assertEqual(result["status"], "ok")

    def test_prepare_sandbox_reuses_existing_without_deleting_it(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch("openshell_contained_workshop.host._run_cli", return_value=completed) as run:
            state = prepare_sandbox(example_root=Path("/example"), sandbox_name="contained")

        self.assertEqual(state, "reused")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][:3], ["policy", "set", "contained"])

    def test_prepare_sandbox_reports_error_phase_recovery(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="\x1b[2mPhase:\x1b[0m Error",
            stderr="",
        )
        with patch("openshell_contained_workshop.host._run_cli", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "sandbox delete contained"):
                prepare_sandbox(example_root=Path("/example"), sandbox_name="contained")


if __name__ == "__main__":
    unittest.main()
