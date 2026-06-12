"""Model construction for the workshop agent."""

from __future__ import annotations

import os

DEFAULT_NVIDIA_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def build_chat_model():
    """Build the chat model configured by environment variables."""

    provider = os.getenv("MODEL_PROVIDER", "nvidia").strip().lower()
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.1"))

    if provider == "nvidia":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        return ChatNVIDIA(
            model=os.getenv("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL),
            api_key=os.getenv("NVIDIA_API_KEY") or None,
            base_url=os.getenv("NVIDIA_BASE_URL") or None,
            temperature=temperature,
            max_completion_tokens=int(os.getenv("MODEL_MAX_TOKENS", "8192")),
        )

    if provider == "langchain":
        from langchain.chat_models import init_chat_model

        model_name = os.getenv("AGENT_MODEL")
        if not model_name:
            msg = "AGENT_MODEL must be set when MODEL_PROVIDER=langchain"
            raise RuntimeError(msg)
        return init_chat_model(model_name)

    msg = f"Unsupported MODEL_PROVIDER={provider!r}. Use 'nvidia' or 'langchain'."
    raise RuntimeError(msg)
