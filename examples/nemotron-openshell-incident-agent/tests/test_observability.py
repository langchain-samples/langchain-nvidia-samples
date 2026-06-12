from __future__ import annotations

import unittest

from openshell_obs_workshop.observability import redact_text, safe_metadata


class ObservabilityTests(unittest.TestCase):
    def test_redacts_known_secret_shapes(self) -> None:
        nvidia_key = "nvapi" + "-example123"
        langsmith_key = "lsv2" + "_pt_example123"
        text = f"NVIDIA_API_KEY={nvidia_key} and LANGSMITH_API_KEY={langsmith_key}"

        redacted = redact_text(text)

        self.assertNotIn(nvidia_key, redacted)
        self.assertNotIn(langsmith_key, redacted)
        self.assertIn("NVIDIA_API_KEY=[REDACTED]", redacted)

    def test_bounds_trace_payload_size(self) -> None:
        redacted = redact_text("x" * 50, max_chars=10)

        self.assertTrue(redacted.startswith("x" * 10))
        self.assertIn("truncated 40 chars", redacted)

    def test_can_omit_trace_payload(self) -> None:
        self.assertEqual(redact_text("sensitive output", max_chars=0), "[omitted]")

    def test_safe_metadata_coerces_and_redacts(self) -> None:
        metadata = safe_metadata({"token": "OPENAI_API_KEY=sk-" + "a" * 30, "count": 3})

        self.assertEqual(metadata["count"], "3")
        self.assertNotIn("sk-" + "a" * 30, metadata["token"])


if __name__ == "__main__":
    unittest.main()
