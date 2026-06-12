from __future__ import annotations

import unittest
from types import SimpleNamespace

from openshell_obs_workshop.backend import OpenShellBackend


class FakeSession:
    id = "fake-sandbox"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def exec(self, argv, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"argv": argv, **kwargs})
        return SimpleNamespace(stdout="ok", stderr="", exit_code=0)


class OpenShellBackendTests(unittest.TestCase):
    def test_execute_sends_multiline_commands_via_stdin(self) -> None:
        session = FakeSession()
        backend = OpenShellBackend(session, default_timeout=30)  # type: ignore[arg-type]

        response = backend.execute("printf 'hello'\nprintf 'world'")

        self.assertEqual(response.exit_code, 0)
        self.assertEqual(session.calls[0]["argv"], ["bash", "-lc", "bash -s"])
        self.assertEqual(session.calls[0]["stdin"], b"printf 'hello'\nprintf 'world'")
        self.assertNotIn("\n", " ".join(session.calls[0]["argv"]))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
