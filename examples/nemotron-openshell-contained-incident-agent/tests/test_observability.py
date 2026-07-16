from __future__ import annotations

import unittest

from openshell_contained_workshop.observability import redact_text, safe_metadata


class ObservabilityTests(unittest.TestCase):
    def test_redacts_known_secret_shapes_and_assignments(self) -> None:
        nvidia_key = "nvapi" + "-example123"
        langsmith_key = "lsv2" + "_pt_example123"

        redacted = redact_text(
            f"NVIDIA_API_KEY={nvidia_key} LANGSMITH_API_KEY={langsmith_key}"
        )

        self.assertNotIn(nvidia_key, redacted)
        self.assertNotIn(langsmith_key, redacted)
        self.assertIn("NVIDIA_API_KEY=[REDACTED]", redacted)

    def test_bounds_and_can_omit_payloads(self) -> None:
        self.assertIn("truncated 40 chars", redact_text("x" * 50, max_chars=10))
        self.assertEqual(redact_text("value", max_chars=0), "[omitted]")

    def test_safe_metadata_coerces_values(self) -> None:
        metadata = safe_metadata({"count": 3, "credential": "API_KEY=placeholder"})

        self.assertEqual(metadata["count"], "3")
        self.assertEqual(metadata["credential"], "API_KEY=[REDACTED]")


if __name__ == "__main__":
    unittest.main()
