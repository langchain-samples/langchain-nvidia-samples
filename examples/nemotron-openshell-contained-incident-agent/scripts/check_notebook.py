#!/usr/bin/env python3
"""Validate the participant notebook without executing live model labs."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_NOTEBOOK = Path("workshop/notebooks/participant_walkthrough.ipynb")
REQUIRED_HEADINGS = (
    "# NVIDIA OpenShell Contained Deep Agent Workshop",
    "## 0. Host Setup",
    "## 2. Build The Contained Runtime",
    "## Lab 1: Prove The Agent Runtime Boundary",
    "## Lab 2: Contained Incident Analysis",
    "## Lab 4: Policy Enforcement From Inside The Agent",
    "## Lab 6: Debugging With LangSmith",
)


def load_notebook(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_notebook(notebook: dict[str, Any], path: Path) -> None:
    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "markdown"
    )
    for heading in REQUIRED_HEADINGS:
        if heading not in markdown:
            raise AssertionError(f"Missing notebook heading: {heading}")
    if "runner.build_agent()" not in markdown:
        raise AssertionError("Notebook is missing the explicit sandbox agent-construction step")

    code_text = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    )
    if "openshell_contained_workshop.agent" in code_text:
        raise AssertionError("The host notebook must not import the contained agent module")
    for required in (
        "prepare_sandbox",
        "invoke_contained_agent",
        "execution_boundary",
        "openshell-contained",
        "lab_trace_urls",
        "Open the traces",
        "/home/sandbox",
        "Artifact-backed incident checkpoint",
        "Verified generic execution checkpoint",
        "Skills and trace-reading contract",
        "Treat model prose as a claim",
    ):
        if required not in code_text:
            raise AssertionError(f"Notebook is missing required runtime behavior: {required}")

    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        ast.parse(source, filename=f"{path}:cell-{index}")
    print("notebook-structure-and-syntax-ok")


def execute_safe_cells(notebook: dict[str, Any], path: Path) -> None:
    namespace: dict[str, Any] = {"__name__": "__notebook_safe_check__"}
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        tags = cell.get("metadata", {}).get("tags", [])
        if "safe-check" not in tags:
            continue
        source = "".join(cell.get("source", []))
        print(f"executing-safe-cell-{index}")
        exec(compile(source, filename=f"{path}:cell-{index}", mode="exec"), namespace)
    print("notebook-safe-cells-ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    parser.add_argument("--execute-safe-cells", action="store_true")
    args = parser.parse_args()
    notebook = load_notebook(args.notebook)
    validate_notebook(notebook, args.notebook)
    if args.execute_safe_cells:
        execute_safe_cells(notebook, args.notebook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
