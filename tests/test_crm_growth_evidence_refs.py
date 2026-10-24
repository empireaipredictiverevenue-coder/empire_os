"""Regression tests for the CRM brief's unique provenance count."""
import unittest
from dataclasses import replace

from empire_os.revenue_crm_search_growth import build_crm_search_growth_brief
from empire_os.search_intelligence.ai_visibility import AiCitationObservation
from empire_os.search_intelligence.backlinks import BacklinkObservation


class GrowthEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.link = BacklinkObservation(
            source_url="https://directory.example/item",
            target_url="https://www.example.com/",
            observed_at="2026-10-24T12:00:00Z",
            provenance=("link:1",),
        )
        self.citation = AiCitationObservation(
            query="roofing", engine="test-engine",
            observed_at="2026-10-24T12:00:00Z",
            cited_url="https://competitor.example/",
            provenance=("answer:1",),
        )

    def brief(self, **changes):
        args = dict(prospect_id="test-account", domain="example.com",
                    query="roofing", engine="test-engine",
                    backlinks=(self.link,), citations=(self.citation,))
        args.update(changes)
        return build_crm_search_growth_brief(**args)

    def test_competitor_analysis_does_not_inflate_evidence(self):
        plain = self.brief()
        gap = self.brief(competitor_domains=("competitor.example",))
        self.assertEqual(plain.evidence_count, 2)
        self.assertEqual(gap.evidence_count, plain.evidence_count)
        self.assertTrue(gap.citation_gap.citation_gap_observed)
        self.assertEqual(gap.evidence_refs, ("answer:1", "link:1"))

    def test_repeated_and_shared_references_count_once(self):
        brief = self.brief(
            backlinks=(replace(self.link, provenance=("shared", " shared ")),),
            citations=(replace(self.citation, provenance=("shared",)),) * 2,
        )
        self.assertEqual(brief.evidence_count, 1)
        self.assertEqual(brief.as_dict()["evidence_refs"], ("shared",))

    def test_out_of_scope_observations_do_not_contribute(self):
        brief = self.brief(
            backlinks=(self.link, replace(self.link, target_url="https://other.example/",
                                         provenance=("other-link",))),
            citations=(self.citation,
                       replace(self.citation, query="other", provenance=("other-query",)),
                       replace(self.citation, engine="other", provenance=("other-engine",))),
        )
        self.assertEqual(brief.evidence_refs, ("answer:1", "link:1"))

    def test_missing_evidence_stays_unavailable(self):
        brief = self.brief(backlinks=(), citations=())
        self.assertEqual(brief.evidence_refs, ())
        self.assertEqual(brief.evidence_count, 0)
        self.assertFalse(brief.ai_visibility.available)
        self.assertIsNone(brief.ai_visibility.empire_cited)
        self.assertEqual(brief.execution_authority, "none")
        self.assertFalse(brief.crm_mutation)

    def test_invalid_reference_fails_closed(self):
        for bad in ("", "  ", None, 42):
            with self.subTest(ref=bad), self.assertRaises(ValueError):
                self.brief(citations=(replace(self.citation, provenance=(bad,)),))


if __name__ == "__main__":
    unittest.main()
