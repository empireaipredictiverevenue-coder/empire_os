"""Challenge local-model research output without promoting guesses."""
from hashlib import sha256
from datetime import datetime, timezone

from empire_os.research.brokerage_editorial_review import review_brokerage_editorial
from empire_os.research.brokerage_decision_brief import build_brokerage_decision_brief
from empire_os.research.brokerage_model_challenge import challenge_research_brief
from scripts.run_brokerage_deep_research_20261021 import run

NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)

def inspected(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Original source"],
        "literal_source_terms_observed": ["dental implants", "dentures"],
    }

def brief():
    return build_brokerage_decision_brief(
        review_brokerage_editorial("GB", inspect_fn=inspected, observed_at=NOW)
    )

def test_model_factual_hallucination_is_rejected():
    report = challenge_research_brief(
        brief(),
        model_fn=lambda prompt: (
            "These practice sites may not be performing well in search rankings "
            "or attracting patients."
        ),
    )
    assert report["status"] == "HELD_MODEL_CONCLUSION_CONTRADICTS_SOURCE_LIMITS"
    assert report["proposed_questions_unverified"] is None
    assert not report["independent_facts_approved"]
    assert not report["outbound_authorized"]

def test_even_good_questions_do_not_grant_editorial_approval():
    prompts = []
    def fake(prompt):
        prompts.append(prompt)
        return ("Which original claims distinguish full-arch from "
                "single-implant treatment? What reuse rights apply?")
    r = challenge_research_brief(brief(), model_fn=fake)
    assert r["status"] == "UNTRUSTED_MODEL_EDITORIAL_QUESTIONS_ONLY"
    assert "reuse rights" in r["proposed_questions_unverified"]
    assert len(prompts) == 1 and "do not recommend contacting" in prompts[0].lower()
    assert r["model_is_reviewer_or_editorial_authority"] is False
    assert not r["customer_use_authorized"]

def test_model_exception_fails_closed_without_breaking_evidence():
    def bad(prompt):
        raise RuntimeError("compute unavailable")
    result = run(country="GB", inspect_fn=inspected,
                 local_model_challenge=True, model_fn=bad)
    assert result["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
    assert result["market_reports"][0]["advisory_model_review"]["status"] == \
        "HELD_LOCAL_MODEL_UNAVAILABLE"
    assert result["market_reports"][0]["editorial_approval"] is False

def test_model_not_called_by_default():
    result = run(country="GB", inspect_fn=inspected)
    assert result["market_reports"][0]["advisory_model_review"]["status"] == \
        "LOCAL_MODEL_NOT_CALLED"



def test_real_llama_cpp_timeout_payload_is_not_misreported_as_a_question():
    timeout = '{"error": "llama_cpp_request_failed:TimeoutError"}'
    r = challenge_research_brief(brief(), model_fn=lambda prompt: timeout)
    assert r["status"] == "HELD_LOCAL_MODEL_PROVIDER_REPORTED_ERROR"
    assert r["model_called"] is True
    assert r["customer_use_authorized"] is False
    assert "proposed_questions_unverified" not in r
