"""NVIDIA model construction for the contained workshop runtime."""

from __future__ import annotations

import os

DEFAULT_NVIDIA_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def build_chat_model():
    """Build the NVIDIA chat model from runtime-injected environment variables."""

    provider = os.getenv("MODEL_PROVIDER", "nvidia").strip().lower()
    if provider != "nvidia":
        msg = f"Unsupported MODEL_PROVIDER={provider!r}. This NVIDIA workshop requires 'nvidia'."
        raise RuntimeError(msg)

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    return ChatNVIDIA(
        model=os.getenv("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL),
        api_key=os.getenv("NVIDIA_API_KEY") or None,
        base_url=os.getenv("NVIDIA_BASE_URL") or None,
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.1")),
        max_completion_tokens=int(os.getenv("MODEL_MAX_TOKENS", "8192")),
    )
