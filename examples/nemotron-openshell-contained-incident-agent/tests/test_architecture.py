from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_runtime_modules_do_not_import_openshell_sdk(self) -> None:
        package = ROOT / "src/openshell_contained_workshop"
        for name in ("agent.py", "backend.py", "runner.py", "tools.py"):
            modules = imported_modules(package / name)
            self.assertFalse(
                any(module == "openshell" or module.startswith("openshell.") for module in modules),
                name,
            )

    def test_host_does_not_import_agent_module(self) -> None:
        package = ROOT / "src/openshell_contained_workshop"

        self.assertNotIn("agent", imported_modules(package / "host.py"))
        self.assertNotIn("agent", imported_modules(package / "__init__.py"))

    def test_docker_context_excludes_secret_files(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for pattern in (".env", "*.pem", "*.key", "*.crt", "credentials.json", ".git/"):
            self.assertIn(pattern, dockerignore)

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("COPY . ", dockerfile)
        self.assertNotIn("NVIDIA_API_KEY=", dockerfile)
        self.assertNotIn("LANGSMITH_API_KEY=", dockerfile)
        self.assertIn("RUN sfw uv sync --frozen", dockerfile)
        self.assertIn("iproute2", dockerfile)

    def test_policy_limits_network_to_nvidia_and_langsmith(self) -> None:
        policy = (ROOT / "workshop/policies/contained-runtime.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("integrate.api.nvidia.com", policy)
        self.assertIn("api.smith.langchain.com", policy)
        self.assertNotIn("host: '*'", policy)


if __name__ == "__main__":
    unittest.main()
