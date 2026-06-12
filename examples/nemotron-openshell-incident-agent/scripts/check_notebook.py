#!/usr/bin/env python3
"""Validate the workshop notebook without running the LLM labs."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_NOTEBOOK_PATH = Path("workshop/notebooks/participant_walkthrough.ipynb")
SETUP_CELL_INDICES = (3, 5, 7, 9, 11, 13)
LAB1_CELL_INDEX = 15
LAB2_CELL_INDEX = 17
ARTIFACT_INSPECTION_CELL_INDEX = 19
GENERIC_TOOLING_CELL_INDEX = 21
POLICY_OBSERVABILITY_CELL_INDEX = 23
SKILLS_READ_CELL_INDEX = 26
SKILLS_ITERATION_CELL_INDEX = 27
TRACE_CHECKLIST_CELL_INDEX = 29
ALL_LAB_CELL_INDICES = (
    LAB1_CELL_INDEX,
    LAB2_CELL_INDEX,
    ARTIFACT_INSPECTION_CELL_INDEX,
    GENERIC_TOOLING_CELL_INDEX,
    POLICY_OBSERVABILITY_CELL_INDEX,
    SKILLS_READ_CELL_INDEX,
    SKILLS_ITERATION_CELL_INDEX,
    TRACE_CHECKLIST_CELL_INDEX,
)


def _load_notebook(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_cells(notebook: dict[str, Any]) -> list[tuple[int, str]]:
    cells: list[tuple[int, str]] = []
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") == "code":
            cells.append((index, "".join(cell.get("source", []))))
    return cells


def check_syntax(notebook: dict[str, Any], notebook_path: Path) -> None:
    for index, source in _code_cells(notebook):
        ast.parse(source, filename=f"{notebook_path}:cell-{index}")
    print("notebook-code-syntax-ok", flush=True)


def execute_cells(notebook: dict[str, Any], indices: tuple[int, ...], notebook_path: Path) -> None:
    namespace: dict[str, Any] = {"__name__": "__notebook_setup_check__"}
    for index, source in _code_cells(notebook):
        if index not in indices:
            continue
        print(f"executing-cell-{index}", flush=True)
        code = compile(source, filename=f"{notebook_path}:cell-{index}", mode="exec")
        exec(code, namespace)
    print("notebook-selected-cells-ok", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebook",
        type=Path,
        default=DEFAULT_NOTEBOOK_PATH,
        help=f"Notebook path to validate. Defaults to {DEFAULT_NOTEBOOK_PATH}.",
    )
    parser.add_argument(
        "--execute-setup",
        action="store_true",
        help="Execute setup/preflight/import cells, but skip LLM lab cells.",
    )
    parser.add_argument(
        "--execute-lab1",
        action="store_true",
        help="Execute setup cells plus Lab 1. This makes a real model call.",
    )
    parser.add_argument(
        "--execute-lab2",
        action="store_true",
        help="Execute setup cells plus Lab 2. This makes real model calls.",
    )
    parser.add_argument(
        "--execute-artifact-inspection",
        action="store_true",
        help="Execute setup cells plus the OpenShell artifact-inspection lab. Lab 2 artifacts must already exist.",
    )
    parser.add_argument(
        "--execute-all-labs",
        action="store_true",
        help="Execute setup cells plus every lab cell. This makes several real model calls.",
    )
    args = parser.parse_args()

    notebook_path = args.notebook
    notebook = _load_notebook(notebook_path)
    check_syntax(notebook, notebook_path)
    if args.execute_all_labs:
        execute_cells(notebook, (*SETUP_CELL_INDICES, *ALL_LAB_CELL_INDICES), notebook_path)
    elif args.execute_lab2:
        execute_cells(notebook, (*SETUP_CELL_INDICES, LAB2_CELL_INDEX), notebook_path)
    elif args.execute_artifact_inspection:
        execute_cells(notebook, (*SETUP_CELL_INDICES, ARTIFACT_INSPECTION_CELL_INDEX), notebook_path)
    elif args.execute_lab1:
        execute_cells(notebook, (*SETUP_CELL_INDICES, LAB1_CELL_INDEX), notebook_path)
    elif args.execute_setup:
        execute_cells(notebook, SETUP_CELL_INDICES, notebook_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
