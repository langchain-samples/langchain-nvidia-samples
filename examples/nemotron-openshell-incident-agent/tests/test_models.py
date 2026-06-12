from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from openshell_obs_workshop.models import DEFAULT_NVIDIA_MODEL, build_chat_model


class ModelConstructionTests(unittest.TestCase):
    def test_nvidia_default_uses_nemotron_3_ultra_and_base_url(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "MODEL_PROVIDER": "nvidia",
                    "NVIDIA_API_KEY": "nvapi-example",
                    "NVIDIA_BASE_URL": "http://127.0.0.1:8000/v1",
                },
                clear=False,
            ),
            patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as chat_nvidia,
        ):
            build_chat_model()

        chat_nvidia.assert_called_once()
        kwargs = chat_nvidia.call_args.kwargs
        self.assertEqual(kwargs["model"], DEFAULT_NVIDIA_MODEL)
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:8000/v1")
        self.assertIn("max_completion_tokens", kwargs)


if __name__ == "__main__":
    unittest.main()
