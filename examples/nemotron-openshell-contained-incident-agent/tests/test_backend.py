from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openshell_contained_workshop.backend import ContainedRuntimeBackend


class ContainedRuntimeBackendTests(unittest.TestCase):
    def test_execute_runs_multiline_script_in_configured_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend = ContainedRuntimeBackend(default_timeout=10, workdir=directory)

            response = backend.execute("printf 'hello\\n'\nprintf 'world\\n'\npwd")

            self.assertEqual(response.exit_code, 0)
            self.assertIn("hello", response.output)
            self.assertIn("world", response.output)
            self.assertIn(directory, response.output)

    def test_execute_returns_timeout_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend = ContainedRuntimeBackend(default_timeout=1, workdir=directory)

            response = backend.execute("sleep 2")

            self.assertEqual(response.exit_code, 124)
            self.assertIn("timed out", response.output)

    def test_upload_and_download_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "nested" / "artifact.txt")
            backend = ContainedRuntimeBackend(default_timeout=10, workdir=directory)

            uploads = backend.upload_files([(path, b"contained")])
            downloads = backend.download_files([path])

            self.assertIsNone(uploads[0].error)
            self.assertIsNone(downloads[0].error)
            self.assertEqual(downloads[0].content, b"contained")

    def test_upload_reports_directory_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend = ContainedRuntimeBackend(default_timeout=10, workdir=directory)

            response = backend.upload_files([(directory, b"not-a-file")])

            self.assertEqual(response[0].error, "is_directory")


if __name__ == "__main__":
    unittest.main()
