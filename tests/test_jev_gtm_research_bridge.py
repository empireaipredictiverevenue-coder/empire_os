"""JEV X shared Vane/OpenManus-inspired research engine: end-to-end OBSERVE gauntlet."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from empire_os.jev_gtm_v2 import build_jev_gtm_decision
from empire_os.jev_gtm_research_bridge import (
    plan_jev_evidence_gap, run_jev_evidence_gap, attach_jev_research_review,
)
from empire_os.research.research_profiles import ResearchProfile

NOW = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
OFFICIAL = "https://www.gov.uk/government/publications/roofing-procurement-guidance"
SHA = sha256(b"fictional official source").hexdigest()


def decision(*, signals=(), outreach=None, verified=True):
    account = {
        "entity_id": "entity:fixture-roof", "tenant_id": "tenant:fixture",
        "opportunity_key": "opportunity:fixture",
        "entity_verified": verified, "tenant_binding_verified": verified,
        "business_name": "Private Fictional Company",
        "description": "roofing services",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "target_product_codes": ["managed_service"],
        "first_party_people": [{"title": "owner"}],
    }
    return build_jev_gtm_decision(
        account=account, signals=signals, as_of=NOW,
        outreach=outreach or {},
    )


def mock_search(log):
    def search(query, num):
        log.append(("search", query, num))
        return {"organic": [{
            "title": "Fictional public UK roofing procurement guidance",
            "link": OFFICIAL, "snippet": "Fictional market opportunity",
            "source_lane": "official", "discovery_engine": "mock",
        }]}
    return search


def mock_inspect(log):
    def inspect(url):
        log.append(("inspect", url))
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "source_url": url,
            "content_sha256": SHA,
            "document_headings": ["Fictional procurement notice"],
            "visible_excerpt": "Private draft content that must not appear in result",
        }
    return inspect


def test_plan_reuses_speed_profile_budgets_and_real_jev_blockers():
    source = decision()
    plan = plan_jev_evidence_gap(
        source, public_niche="roofing", public_market="Manchester",
    )
    assert plan["status"] == "PLANNED_PUBLIC_RESEARCH"
    assert plan["budget"] == {"max_queries": 2, "max_pages": 4}
    assert plan["public_evidence_blockers"] == ["fresh_evidenced_signal_missing"]
    assert "suppression_readback_missing" in plan["canonical_authority_blockers"]
    assert "Private Fictional Company" not in str(plan)
    assert source["tenant_id"] not in plan["question"]
    assert source["entity_id"] not in plan["question"]
    assert plan["outbound_approved"] is False
    assert plan["paid_api_budget_gbp"] == 0
    assert plan["execution_authority"] == "none"


def test_reuses_same_plan_with_stable_fingerprint():
    source = decision()
    p = dict(public_niche="roofing", public_market="Manchester")
    a = plan_jev_evidence_gap(source, **p)
    b = plan_jev_evidence_gap(source, **p)
    assert a == b
    assert a["plan_fingerprint"] != plan_jev_evidence_gap(
        source, public_niche="solar", public_market="Manchester",
    )["plan_fingerprint"]


def test_end_to_end_declarative_research_receipt_and_reused_decision():
    source = decision()
    original = deepcopy(source)
    log = []

    def synthesize(question, inspected):
        assert len(inspected) == 1
        assert inspected[0]["original_page_inspected"] is True
        return {"claims": [{"claim": "Fictional cited opportunity draft", "source_ids": ["S1"]}]}

    result = run_jev_evidence_gap(
        source, public_niche="roofing", public_market="Manchester",
        search_fn=mock_search(log), inspect_fn=mock_inspect(log),
        synthesize_fn=synthesize,
    )
    assert source == original
    assert result["status"] == "DRAFT_WITH_INSPECTED_CITATIONS"
    assert result["source_count"] == 1
    assert result["inspected_source_count"] == 1
    assert result["sources"][0]["url"] == OFFICIAL
    assert result["sources"][0]["content_sha256"] == SHA
    assert result["sources"][0]["claim_accuracy_verified"] is False
    assert len(result["claims_unverified"]) == 1
    assert result["claims_unverified"][0]["source_ids"] == ["S1"]
    assert "Fictional cited opportunity draft" not in str(result)
    assert "Private draft content" not in str(result)
    assert result["commercial_promotion_authorized"] is False
    assert result["contact_clearance_verified"] is False
    assert result["outbound_sent"] is False
    assert result["database_write"] is False
    assert result["research_steps"][-1] == {"id": "commercial", "status": "blocked"}
    assert len([c for c in log if c[0] == "search"]) <= 2

    attachment = attach_jev_research_review(source, result)
    assert attachment["jev_recommendation_unchanged"] == original["action"]
    assert attachment["jev_blockers_unchanged"] == original["blockers"]
    assert attachment["buyer_intent_verified"] is False
    assert attachment["founder_review_required"] is True
    assert attachment["execution_authority"] == "none"


def test_uninspected_search_results_are_not_cited_or_verified():
    log = []
    def noinspect(url):
        log.append(("inspect",url))
        return {"status": "DISCOVERY_SOURCE_NOT_PRIMARY"}
    result = run_jev_evidence_gap(
        decision(), public_niche="roofing", public_market="Manchester",
        search_fn=mock_search(log), inspect_fn=noinspect,
        synthesize_fn=lambda *_: pytest.fail("synthesis should not run"),
    )
    assert result["source_count"] == 1
    assert result["inspected_source_count"] == 0
    assert result["claims_unverified"] == []
    assert result["status"] == "INSUFFICIENT_PRIMARY_EVIDENCE"


def test_search_empty_fails_truthfully():
    result = run_jev_evidence_gap(
        decision(), public_niche="roofing", public_market="Manchester",
        search_fn=lambda q, num: {"organic": []},
        inspect_fn=lambda u: pytest.fail("no discovered URL"),
    )
    assert result["source_count"] == 0
    assert result["inspected_source_count"] == 0
    assert result["status"] == "INSUFFICIENT_PRIMARY_EVIDENCE"
    assert result["commercial_promotion_authorized"] is False


def test_suppressed_contact_forces_market_only_and_no_personal_fields():
    source = decision(outreach={
        "suppression_checked": True, "suppressed": True, "suppression_state": "SUPPRESSED"
    })
    plan = plan_jev_evidence_gap(
        source, public_niche="roofing", public_market="Manchester",
    )
    assert plan["scope"] == "MARKET_ONLY"
    assert plan["outbound_approved"] is False
    assert "Private Fictional Company" not in str(plan)


def test_unverified_source_identity_is_not_repaired_by_web():
    source = decision(verified=False)
    assert "canonical_identity_or_tenant_binding_unverified" in source["blockers"]
    plan = plan_jev_evidence_gap(
        source, public_niche="roofing", public_market="Manchester",
    )
    assert "canonical_identity_or_tenant_binding_unverified" in plan["canonical_authority_blockers"]
    assert plan["buyer_intent_verified"] is False


@pytest.mark.parametrize("bad_niche,bad_market", [
    ("private@example.com", "Manchester"),
    ("roofing", "token:do-not-leak"),
    ("roofing", ""),
    ("roofing", "https://metadata.internal"),
])
def test_private_or_malformed_market_context_never_searches(bad_niche, bad_market):
    calls = []
    result = run_jev_evidence_gap(
        decision(), public_niche=bad_niche, public_market=bad_market,
        search_fn=lambda *_a, **_kw: calls.append(True),
        inspect_fn=lambda *_: calls.append(True),
    )
    assert result["status"] == "BLOCKED_PUBLIC_CONTEXT_MISSING"
    assert result["source_count"] == 0
    assert calls == []


@pytest.mark.parametrize("depth", ["unlimited", "infinite", "full_auto"])
def test_unbounded_research_depth_rejected(depth):
    with pytest.raises(ValueError, match="unsupported"):
        plan_jev_evidence_gap(
            decision(), public_niche="roofing", public_market="Manchester", depth=depth
        )


def test_invalid_JEV_decision_cannot_grant_research_authority():
    source = decision()
    source["execution_authority"] = "send"
    with pytest.raises(ValueError, match="non-executing"):
        plan_jev_evidence_gap(
            source, public_niche="roofing", public_market="Manchester",
        )


def test_decision_fingerprint_and_research_receipt_cannot_cross_opportunities():
    a, b = decision(), decision(outreach={"suppressed": True})
    assert a["decision_fingerprint"] != b["decision_fingerprint"]
    out = run_jev_evidence_gap(
        a, public_niche="roofing", public_market="Manchester",
        search_fn=lambda *_a, **_kw: {"organic": []},
        inspect_fn=lambda *_: {},
    )
    with pytest.raises(ValueError, match="untrusted"):
        attach_jev_research_review(b, out)


def test_no_public_gap_results_in_no_external_calls():
    signal = {
        "signal_id": "s1", "signal_type": "hiring",
        "entity_id": "entity:fixture-roof", "tenant_id": "tenant:fixture",
        "source_id": "official:example", "truth_class": "OBSERVED",
        "observed_at": NOW.isoformat(), "evidence_refs": ["proof:public:s1"],
    }
    source = decision(signals=[signal])
    calls = []
    result = run_jev_evidence_gap(
        source, public_niche="roofing", public_market="Manchester",
        search_fn=lambda *_a, **_kw: calls.append(True),
        inspect_fn=lambda *_: calls.append(True),
    )
    assert result["status"] == "CANONICAL_OR_NO_PUBLIC_EVIDENCE_GAP"
    assert calls == []
    assert result["canonical_decision_modified"] is False


def test_malicious_ssrf_discovery_result_not_inspected():
    calls = []
    result = run_jev_evidence_gap(
        decision(), public_niche="roofing", public_market="Manchester",
        search_fn=lambda *_a, **_kw: {"organic": [
            {"link": "http://169.254.169.254/latest/meta-data"},
            {"link": "http://localhost:8080/private"},
            {"link": "file:///etc/passwd"},
            {"link": "https://api.private.internal/admin"},
        ]},
        inspect_fn=lambda *_: calls.append(True),
    )
    assert result["source_count"] == 0
    assert calls == []


def test_bounded_high_cardinality_search_and_page_budget():
    calls = []
    def search(query, num):
        calls.append(query)
        return {"organic": [
            {"link": f"https://www.gov.uk/example/{i}", "title": "example"}
            for i in range(100)
        ]}
    result = run_jev_evidence_gap(
        decision(), public_niche="roofing", public_market="Manchester",
        depth="speed", search_fn=search,
        inspect_fn=lambda url: {"status": "DISCOVERY_SOURCE_NOT_PRIMARY"},
    )
    assert len(calls) <= 2
    assert result["source_count"] <= 4
    assert result["pages_considered"] <= 4


def test_original_research_sources_are_shared_not_third_party_runtime():
    assert ResearchProfile(mode="balanced").validate().max_queries == 4
    assert ResearchProfile(mode="quality").validate().max_pages == 12
    assert ResearchProfile(mode="speed").validate().max_queries == 2
