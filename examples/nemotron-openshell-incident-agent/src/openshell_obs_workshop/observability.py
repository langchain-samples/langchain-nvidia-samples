"""Small helpers for safe LangSmith instrumentation."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"lsv2_pt_[A-Za-z0-9_\-]+"),
    re.compile(r"nvapi-[A-Za-z0-9_\-]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"AIza[A-Za-z0-9\-_]{20,}"),
]

_ENV_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z0-9_]*)=([^\s]+)"
)


def tracing_enabled() -> bool:
    """Return true when LangSmith tracing should create explicit custom spans."""

    flag = os.getenv("LANGSMITH_TRACING", "").strip().lower()
    return flag in {"1", "true", "yes", "on"} and bool(os.getenv("LANGSMITH_API_KEY"))


def redact_text(value: Any, *, max_chars: int = 4000) -> str:
    """Convert a value to text, redact likely secrets, and bound trace payload size."""

    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    text = _ENV_ASSIGNMENT.sub(r"\1=[REDACTED]", text)

    if max_chars <= 0:
        return "[omitted]"

    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return f"{text[:max_chars]}\n...[truncated {omitted} chars]"


def safe_metadata(metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return metadata with values redacted and coerced to primitive text."""

    if not metadata:
        return {}
    return {str(key): redact_text(value, max_chars=500) for key, value in metadata.items()}


@contextmanager
def optional_trace(
    *,
    name: str,
    run_type: str,
    inputs: Mapping[str, Any] | None = None,
    tags: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[Any | None]:
    """Create a LangSmith span only when tracing is configured.

    The workshop should still run without LangSmith credentials, so this helper
    degrades to a no-op context manager when tracing is disabled or unavailable.
    """

    if not tracing_enabled():
        yield None
        return

    try:
        import langsmith as ls
    except Exception:  # pragma: no cover - best-effort optional integration
        yield None
        return

    redacted_inputs = safe_metadata(inputs)
    with ls.trace(
        name=name,
        run_type=run_type,
        inputs=redacted_inputs,
        tags=tags or [],
        metadata=safe_metadata(metadata),
    ) as run:
        yield run


def end_trace(run: Any | None, *, outputs: Mapping[str, Any] | None = None) -> None:
    """Safely attach redacted outputs to an optional LangSmith run."""

    if run is None:
        return
    run.end(outputs=safe_metadata(outputs))
