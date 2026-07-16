"""Keep tests local and deterministic regardless of the developer's shell environment."""

from __future__ import annotations

import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
