from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReplicationPackagingTests(unittest.TestCase):
    def test_synthetic_log_fixture_is_present_and_unignored(self) -> None:
        fixture = ROOT / "workshop/data/sample_app.log"
        lines = fixture.read_text(encoding="utf-8").splitlines()
        example_gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertEqual(len(lines), 37)
        self.assertIn("!workshop/data/sample_app.log", example_gitignore)

    def test_readme_covers_clean_machine_setup_and_recovery(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "uv sync --extra notebook --extra dev",
            "NVIDIA OpenShell quickstart",
            "OPENSHELL_VERSION=v0.0.51",
            "For hosted NVIDIA NIM, leave",
            "NVIDIA_BASE_URL",
            "ghcr.io/nvidia/openshell/gateway@sha256:",
            "uv run openshell status",
            "Connection refused",
            "mTLS certificates",
            "uv run openshell sandbox delete contained-agent-workshop",
            "503 ResourceExhausted",
        ):
            self.assertIn(required, readme)

    def test_preflight_checks_fixture_and_prints_actionable_help(self) -> None:
        preflight = (ROOT / "scripts/check_env.py").read_text(encoding="utf-8")

        self.assertIn('Path("workshop/data/sample_app.log")', preflight)
        self.assertIn("OpenShell gateway help:", preflight)
        self.assertNotIn("sfw on PATH", preflight)

    def test_committed_notebook_has_no_execution_or_personal_output(self) -> None:
        notebook_path = ROOT / "workshop/notebooks/participant_walkthrough.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        serialized = json.dumps(notebook)

        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("Documents/Partners", serialized)
        self.assertNotIn("smith.langchain.com/o/", serialized)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])


if __name__ == "__main__":
    unittest.main()
