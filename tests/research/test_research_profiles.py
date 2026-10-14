"""Vane-style research choice and OpenManus-inspired gated step receipts."""
import unittest

from empire_os.research.research_profiles import (
    ResearchProfile, build_research_plan, research_with_profile,
)


class ProfileTests(unittest.TestCase):
    def test_quality_includes_source_lanes_and_bounded_budget(self):
        plan = build_research_plan(
            "solar installation opportunities",
            ResearchProfile(
                mode="quality",
                country="GB",
                sector="roofing",
                lanes=("official", "community", "academic", "company"),
            ),
        )
        self.assertEqual(plan["limits"]["max_queries"], 8)
        self.assertEqual(plan["limits"]["max_rounds"], 3)
        self.assertEqual(plan["limits"]["max_pages"], 12)
        self.assertTrue(any("site:reddit.com" in q for q in plan["queries"]))
        self.assertTrue(any("official primary" in q for q in plan["queries"]))
        self.assertEqual(plan["steps"][-1]["status"], "blocked")
        self.assertFalse(plan["outbound_authorized"])

    def test_speed_restricts_depth(self):
        plan = build_research_plan(
            "local buyers", ResearchProfile(mode="speed", lanes=("web", "community"))
        )
        self.assertEqual(len(plan["queries"]), 2)
        self.assertEqual(plan["limits"]["max_rounds"], 1)

    def test_bad_lanes_and_modes_refused(self):
        for profile in (
            ResearchProfile(mode="unbounded"),
            ResearchProfile(lanes=("browser_execute",)),
            ResearchProfile(lanes=()),
            ResearchProfile(lanes=("web", "web")),
            ResearchProfile(country="UNKNOWN"),
        ):
            with self.subTest(profile=profile):
                with self.assertRaises(ValueError):
                    build_research_plan("buyer evidence", profile)

    def test_no_sources_blocks_commercial_and_draft(self):
        value = research_with_profile(
            "roofing",
            profile=ResearchProfile(mode="balanced", lanes=("official",)),
            search_fn=lambda q, num: {"organic": []},
            inspect_fn=lambda url: {"status": "UNAVAILABLE"},
        )
        states = {row["id"]: row["status"] for row in value["steps"]}
        self.assertEqual(states["inspect"], "blocked")
        self.assertEqual(states["synthesize"], "blocked")
        self.assertEqual(states["commercial"], "blocked")
        self.assertEqual(value["evidence"]["source_count"], 0)

    def test_inspected_draft_remains_unverified(self):
        result = research_with_profile(
            "legal sector",
            profile=ResearchProfile(mode="speed", lanes=("official",)),
            search_fn=lambda q, num: {"organic": [{"url": "https://www.gov.uk/legal"}]},
            inspect_fn=lambda url: {
                "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
                "content_sha256": "f" * 64,
                "document_headings": ["Official legal information"],
            },
            synthesize_fn=lambda q, sources: {
                "claims": [{"claim": "A source observation", "source_ids": ["S1"]}]
            },
        )
        self.assertEqual(result["status"], "DRAFT_WITH_INSPECTED_CITATIONS")
        self.assertFalse(result["evidence"]["draft_claims"][0]["factual_accuracy_verified"])
        self.assertEqual(result["steps"][-1]["status"], "blocked")
        self.assertFalse(result["evidence"]["production_activation"])


if __name__ == "__main__":
    unittest.main()
