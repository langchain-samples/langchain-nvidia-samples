from __future__ import annotations

import unittest
from unittest.mock import patch

from deepagents.backends.protocol import ExecuteResponse

from openshell_contained_workshop.tools import run_policy_boundary_demo


class PolicyToolTests(unittest.TestCase):
    @patch("openshell_contained_workshop.tools.ContainedRuntimeBackend")
    def test_policy_demo_uses_user_owned_read_only_home(self, backend_class) -> None:
        backend = backend_class.return_value
        backend.execute.return_value = ExecuteResponse(
            output="expected",
            exit_code=0,
            truncated=False,
        )

        run_policy_boundary_demo.invoke({})

        commands = [call.args[0] for call in backend.execute.call_args_list]
        self.assertTrue(any(command.startswith("id\n") for command in commands))
        self.assertTrue(any("/sandbox/policy_allowed.txt" in command for command in commands))
        self.assertTrue(any("/home/sandbox/policy_denied.txt" in command for command in commands))
        self.assertFalse(any("/etc/policy_denied.txt" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
