from __future__ import annotations

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
            "command -v sfw",
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
        self.assertIn("Socket Firewall help:", preflight)


if __name__ == "__main__":
    unittest.main()
