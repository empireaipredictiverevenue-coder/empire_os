"""Tests for the first-party search adapter with no live network."""
import unittest

from empire_os.research.empire_search_adapter import research_with_empire_search


class AdapterTests(unittest.TestCase):
    def test_observation_mode_and_existing_bindings(self):
        calls = []
        value = research_with_empire_search(
            "local buyer issues",
            search_fn=lambda q, num: {"organic": [{"url": "https://gov.uk/notice"}]},
            inspect_fn=lambda url: (calls.append(url) or {
                "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
                "content_sha256": "0" * 64,
                "document_headings": ["Notice"],
            }),
        )
        self.assertEqual(value["mode"], "OBSERVE")
        self.assertTrue(value["provider_binding"].startswith("empire."))
        self.assertTrue(value["inspector_binding"].startswith("empire."))
        self.assertEqual(calls, ["https://gov.uk/notice"])
        self.assertFalse(value["outbound_sent"])
        self.assertFalse(value["database_write"])


if __name__ == "__main__":
    unittest.main()
