"""Negative and positive contract tests for OBSERVE-only research intake."""
import unittest

from empire_os.research.deep_research_intake import (
    ResearchLimits,
    _public_url,
    run_research,
)


def inspected(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": "b" * 64,
        "document_headings": ["Annual industry report"],
        "claim_accuracy_verified": False,
    }


class ResearchIntakeTests(unittest.TestCase):
    def test_bounded_deduplicated_and_safe_urls(self):
        calls = []
        inspected_urls = []

        def search(q, num):
            calls.append((q, num))
            return {"organic": [
                {"link": "https://example.org/report", "title": "Report", "snippet": "A"},
                {"link": "https://example.org/report", "title": "Duplicate"},
                {"link": "http://127.0.0.1/private", "title": "SSRF"},
                {"link": "https://example.net/report", "title": "Report 2"},
            ]}

        def inspection(url):
            inspected_urls.append(url)
            return inspected(url)

        result = run_research(
            "UK solar activity",
            search_fn=search,
            inspect_fn=inspection,
            limits=ResearchLimits(max_queries=9, max_pages=1, results_per_query=5),
        )
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["budget"]["max_queries"], 8)
        self.assertEqual(result["budget"]["pages_considered"], 1)
        self.assertEqual(inspected_urls, ["https://example.org/report"])
        self.assertEqual(result["source_count"], 1)
        self.assertTrue(result["source_observations"][0]["original_page_inspected"])
        self.assertFalse(result["source_observations"][0]["claim_accuracy_verified"])
        self.assertFalse(result["database_write"])
        self.assertFalse(result["outbound_authorized"])
        self.assertEqual(result["status"], "EVIDENCE_READY_FOR_SYNTHESIS")

    def test_provider_failure_abstains(self):
        def broken(q, num):
            raise TimeoutError("provider secret should not be returned")

        result = run_research(
            "Roofing buyers", search_fn=broken, inspect_fn=inspected,
            limits=ResearchLimits(max_queries=1)
        )
        self.assertEqual(result["status"], "INSUFFICIENT_PRIMARY_EVIDENCE")
        self.assertEqual(result["searches"][0]["error_type"], "TimeoutError")
        self.assertNotIn("secret", str(result))
        self.assertEqual(result["draft_claims"], [])

    def test_inspector_failure_cannot_verify_claims(self):
        result = run_research(
            "Roofing buyers",
            initial_queries=["one"],
            search_fn=lambda q, num: {"organic": [{"url": "https://public.org/a"}]},
            inspect_fn=lambda url: {"status": "DOCUMENT_ACCESS_UNAVAILABLE"},
            synthesize_fn=lambda q, sources: {
                "claims": [{"claim": "Has high demand", "source_ids": ["S1"]}]
            },
        )
        self.assertEqual(result["original_pages_inspected"], 0)
        self.assertEqual(result["draft_claims"], [])
        self.assertEqual(result["status"], "INSUFFICIENT_PRIMARY_EVIDENCE")

    def test_model_claims_require_inspected_source_ids(self):
        result = run_research(
            "Buyer demand",
            initial_queries=["buyer demand"],
            search_fn=lambda q, num: {"organic": [{"url": "https://public.org/a"}]},
            inspect_fn=inspected,
            synthesize_fn=lambda q, sources: {"claims": [
                {"claim": "Supported observation", "source_ids": ["S1"]},
                {"claim": "Fabricated citation", "source_ids": ["S999"]},
                {"claim": "Missing citation", "source_ids": []},
            ]},
        )
        self.assertEqual(len(result["draft_claims"]), 1)
        self.assertEqual(result["rejected_unsupported_claims"], 2)
        self.assertFalse(result["draft_claims"][0]["factual_accuracy_verified"])
        self.assertEqual(result["status"], "DRAFT_WITH_INSPECTED_CITATIONS")

    def test_followup_questions_are_bounded(self):
        terms = []

        def search(q, num):
            terms.append(q)
            return {"organic": []}

        result = run_research(
            "UK legal services",
            initial_queries=["original"],
            search_fn=search, inspect_fn=inspected,
            follow_up_fn=lambda question, sources, history: [
                "followup", "followup", "second followup",
            ],
            limits=ResearchLimits(max_queries=2, max_rounds=2),
        )
        self.assertEqual(terms, ["original", "followup"])
        self.assertEqual(result["budget"]["searches_executed"], 2)
        self.assertEqual(result["searches"][1]["round"], 2)

    def test_url_restrictions(self):
        self.assertIsNone(_public_url("file:///etc/passwd"))
        self.assertIsNone(_public_url("https://user:pass@example.com/a"))
        self.assertIsNone(_public_url("http://localhost/"))
        self.assertIsNone(_public_url("http://169.254.169.254/"))
        self.assertIsNone(_public_url("https://10.1.2.3/"))
        self.assertIsNone(_public_url("https://evil.local/"))
        self.assertIsNotNone(_public_url("https://example.org/research"))

    def test_empty_question_fails(self):
        with self.assertRaises(ValueError):
            run_research("", search_fn=lambda q, num: {}, inspect_fn=inspected)


if __name__ == "__main__":
    unittest.main()
