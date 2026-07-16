from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from openshell_contained_workshop.models import DEFAULT_NVIDIA_MODEL, build_chat_model


class ModelConstructionTests(unittest.TestCase):
    def test_nvidia_model_uses_runtime_configuration(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "MODEL_PROVIDER": "nvidia",
                    "NVIDIA_API_KEY": "placeholder",
                    "NVIDIA_BASE_URL": "http://127.0.0.1:8000/v1",
                },
                clear=False,
            ),
            patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as chat_nvidia,
        ):
            build_chat_model()

        kwargs = chat_nvidia.call_args.kwargs
        self.assertEqual(kwargs["model"], DEFAULT_NVIDIA_MODEL)
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:8000/v1")
        self.assertIn("max_completion_tokens", kwargs)

    def test_rejects_non_nvidia_provider(self) -> None:
        with patch.dict(os.environ, {"MODEL_PROVIDER": "other"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "requires 'nvidia'"):
                build_chat_model()


if __name__ == "__main__":
    unittest.main()
