"""Regression checks for host memory routes; no gateway or API keys required."""

import importlib.util
import os
import shutil
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch


class MemoryRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.example_dir = Path(temporary.name) / "example"
        project_dir = Path(__file__).resolve().parents[1]
        self.source_dir = self.example_dir / "src"
        self.memory_dir = self.example_dir / "memory"
        shutil.copytree(
            project_dir / "src", self.source_dir,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(project_dir / "memory", self.memory_dir)
        self.original_source = {
            path.name: path.read_bytes() for path in self.source_dir.glob("*.py")
        }

        # Load the actual backend from a disposable example so writes cannot
        # modify the checkout and __file__ resolves as it would for a user.
        spec = importlib.util.spec_from_file_location(
            "memory_test_backend", self.source_dir / "backend.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.session = Mock()
        self.enterContext(patch.object(
            self.module.SandboxClient, "from_active_cluster", return_value=Mock()
        ))
        self.enterContext(patch.object(
            self.module, "SandboxSession", return_value=self.session
        ))
        self.enterContext(patch.dict(os.environ, {"OPENSHELL_SANDBOX_NAME": "test"}))
        with chdir(self.example_dir):
            self.backend = self.module.create_backend(None)

    def assert_source_unchanged(self):
        self.assertEqual(
            self.original_source,
            {path.name: path.read_bytes() for path in self.source_dir.glob("*.py")},
        )

    def test_memory_loads_and_edits_persist(self):
        self.assertIn("# Agent Memory", self.backend.read("/memory/AGENTS.md"))
        result = self.backend.edit(
            "/memory/AGENTS.md", "# Agent Memory", "# Updated Agent Memory"
        )
        self.assertIsNone(result.error)
        with chdir(self.example_dir):
            reopened = self.module.create_backend(None)
        self.assertIn("# Updated Agent Memory", reopened.read("/memory/AGENTS.md"))
        self.assert_source_unchanged()
        self.session.exec.assert_not_called()

    def test_memory_file_operations_leave_source_untouched(self):
        for filename in ("agent.py", "backend.py", "prompts.py"):
            with self.subTest(filename=filename):
                path = f"/memory/{filename}"
                self.assertTrue(self.backend.read(path).startswith("Error"))
                self.assertIsNotNone(self.backend.edit(path, "import", "changed").error)
                self.assertIsNone(self.backend.write(path, "memory-only data").error)
                result = self.backend.upload_files([(path, b"replacement memory data")])
                self.assertIsNone(result[0].error)
                self.assertEqual(
                    self.backend.download_files([path])[0].content,
                    b"replacement memory data",
                )
                self.assertEqual(
                    (self.memory_dir / filename).read_bytes(), b"replacement memory data"
                )
                self.assert_source_unchanged()
        self.session.exec.assert_not_called()

    def test_local_routes_are_independent_of_working_directory(self):
        # Starting inside src/ must not redirect memory or skills into source.
        with chdir(self.source_dir):
            backend = self.module.create_backend(None)
            self.assertIn("# Agent Memory", backend.read("/memory/AGENTS.md"))
            for route in ("memory", "skills"):
                self.assertIsNone(backend.write(f"/{route}/note.txt", route).error)
                self.assertEqual((self.example_dir / route / "note.txt").read_text(), route)
                self.assertFalse((self.source_dir / route).exists())
        self.assert_source_unchanged()
        self.session.exec.assert_not_called()

    def test_parent_traversal_cannot_reach_source(self):
        for route in ("memory", "skills"):
            with self.subTest(route=route):
                path = f"/{route}/../src/agent.py"
                with self.assertRaises(ValueError):
                    self.backend.read(path)
                with self.assertRaises(ValueError):
                    self.backend.edit(path, "import", "changed")
                result = self.backend.upload_files([(path, b"replacement")])
                self.assertEqual(result[0].error, "invalid_path")
        self.assert_source_unchanged()
        self.session.exec.assert_not_called()

    def test_symlink_cannot_reach_source(self):
        for route in ("memory", "skills"):
            with self.subTest(route=route):
                directory = self.example_dir / route
                directory.mkdir(exist_ok=True)
                (directory / "source").symlink_to(self.source_dir, target_is_directory=True)
                path = f"/{route}/source/agent.py"
                with self.assertRaises(ValueError):
                    self.backend.read(path)
                with self.assertRaises(ValueError):
                    self.backend.edit(path, "import", "changed")
                result = self.backend.upload_files([(path, b"replacement")])
                self.assertEqual(result[0].error, "invalid_path")
        self.assert_source_unchanged()
        self.session.exec.assert_not_called()

    def test_execution_still_uses_openshell(self):
        self.session.exec.return_value = SimpleNamespace(stdout="ok", stderr="", exit_code=0)
        result = self.backend.execute("printf ok", timeout=5)
        self.assertEqual(result.output, "ok")
        self.session.exec.assert_called_once_with(["bash", "-c", "printf ok"], timeout_seconds=5)


if __name__ == "__main__":
    unittest.main()
