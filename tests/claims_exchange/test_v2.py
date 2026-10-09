from datetime import date, timedelta

import pytest

from empire_os.claims_exchange.controls import (
    candidate_readiness, offer_compliance, classify_signal, safe_https_source,
    reject_sensitive_input
)
from empire_os.claims_exchange.economics import b2b_scenario
from empire_os.claims_exchange.pipeline import build_snapshot

TODAY = date(2026, 10, 9)


def sample(kind="contractor", entity="contractor-1", jurisdiction="TX"):
    kinds = ["identity", "service", "territory", "public_contact_route"]
    if kind == "licensed_claims_partner":
        kinds.append("licensed_status")
    if kind in ("carrier", "managed_repair_network"):
        kinds += ["buyer_demand", "buyer_capacity"]
    return {
        "entity_id": entity, "kind": kind, "jurisdiction": jurisdiction,
        "company_name": "Sample Company", "public_domain": f"{entity}.example.org",
        "services": ["roofing"],
        "evidence": [{
            "kind": e, "observed_at": TODAY.isoformat(), "verified": True,
            "verified_by": "independent_upstream_verifier",
            "source_type": ("official_registry" if e == "licensed_status"
                            else "first_party"),
            "source_url": f"https://{entity}.example.org/business",
        } for e in kinds],
    }


def test_verified_company_ready_but_no_outbound():
    r = candidate_readiness(sample(), as_of=TODAY)
    assert r["review_state"] == "FOUNDER_REVIEW_READY"
    assert not r["outbound_authorized"] and not r["quote_authorized"]


@pytest.mark.parametrize("key", [
    "claimant_name", "homeowner_email", "policy_number", "claim_number", "ssn",
])
def test_sensitive_claim_fields_blocked(key):
    with pytest.raises(ValueError, match="sensitive_claim_person_data_blocked"):
        reject_sensitive_input({"nested": [{"details": {key: "private"}}]})


@pytest.mark.parametrize("url", [
    "http://example.org", "https://127.0.0.1/hi", "https://localhost/hi",
    "https://admin:pass@example.org/", "https://example.test/", "",
])
def test_unsafe_source_provenance_rejected(url):
    assert not safe_https_source(url)


def test_stale_verified_item_is_not_current_evidence():
    c = sample()
    c["evidence"][0]["observed_at"] = (TODAY - timedelta(days=130)).isoformat()
    r = candidate_readiness(c, as_of=TODAY)
    assert "identity" in r["missing_evidence"]
    assert "stale_or_future_evidence" in r["evidence"]["rejected_reasons"]


def test_future_evidence_rejected():
    c = sample()
    c["evidence"][1]["observed_at"] = (TODAY + timedelta(days=2)).isoformat()
    assert "service" in candidate_readiness(c, as_of=TODAY)["missing_evidence"]


def test_false_upstream_verification_rejected():
    c = sample()
    c["evidence"][0]["verified"] = False
    assert "identity" in candidate_readiness(c, as_of=TODAY)["missing_evidence"]


def test_missing_verifier_rejected():
    c = sample()
    c["evidence"][0].pop("verified_by")
    assert "identity" in candidate_readiness(c, as_of=TODAY)["missing_evidence"]


def test_licence_cannot_be_self_attested():
    c = sample("licensed_claims_partner")
    c["evidence"][-1]["source_type"] = "first_party"
    assert "licensed_status" in candidate_readiness(c, as_of=TODAY)["missing_evidence"]


def test_company_contact_requires_first_party():
    c = sample()
    c["evidence"][3]["source_type"] = "published_business_page"
    assert "public_contact_route" in candidate_readiness(c, as_of=TODAY)["missing_evidence"]


def test_hidden_claim_contingency_blocks_flat_fee():
    r = offer_compliance({"basis": "fixed_service", "jurisdiction": "TX",
                          "compensation_tied_to_claim": True})
    assert r["quote_state"] == "BLOCKED_CLAIMS_COMPENSATION_OR_REFERRAL"
    assert r["outbound_authorized"] is False


def test_saas_for_claim_adjuster_requires_specialist_review():
    r = offer_compliance({"basis": "subscription", "jurisdiction": "FL",
                          "counterparty_type": "licensed_claims_partner"})
    assert r["quote_state"] == "BLOCKED_CLAIMS_COMPENSATION_OR_REFERRAL"


@pytest.mark.parametrize("basis", [
    "claim_referral", "settlement_percentage", "repair_contract_percentage",
    "claim_qualified_opportunity", "qualified_opportunity"
])
def test_regulated_pricing_stays_blocked(basis):
    r = offer_compliance({"basis": basis, "jurisdiction": "FL"})
    assert r["quote_state"].startswith("BLOCKED")
    assert r["settlement_fee_authorized"] is False


def test_valid_noncontingent_b2b_subscription_still_requires_founder_review():
    r = offer_compliance({"basis": "subscription", "jurisdiction": "TX"})
    assert r["quote_state"] == "FOUNDER_TERMS_REVIEW"
    assert not r["quote_authorized"]


def test_weather_event_never_creates_claimant():
    r = classify_signal({"kind": "storm_alert", "verified": True,
                         "source_url": "https://api.weather.gov/alerts/active",
                         "observed_at": TODAY.isoformat(),
                         "entity_id": "contractor-1"}, as_of=TODAY)
    assert r["status"] == "CONTEXT_ONLY"
    assert "claimant" not in r


def test_stale_intent_rejected():
    r = classify_signal({"kind": "business_pain", "verified": True,
                         "source_url": "https://example.org/forum",
                         "observed_at": "2024-10-09"}, as_of=TODAY)
    assert r["status"] == "REJECTED"


def test_bounded_queue_dedupe_and_no_sales_execution():
    c = sample()
    result = build_snapshot({"candidates": [c, dict(c)]}, as_of=TODAY)
    assert result["summary"]["unique_candidates"] == 1
    assert result["summary"]["exact_duplicates"] == 1
    assert result["summary"]["actual_revenue"] == 0
    assert result["execution_authority"] == "none"


def test_conflicting_identity_quarantined_not_selected():
    c = sample()
    d = sample(kind="carrier")
    r = build_snapshot({"candidates": [c, d]}, as_of=TODAY)
    assert r["summary"]["unique_candidates"] == 0
    assert r["summary"]["conflicting_identity_groups_quarantined"] == 1


def test_context_doesnt_grant_founder_readiness():
    c = sample()
    c["evidence"] = []
    r = build_snapshot({"candidates": [c], "signals": [{
        "kind": "storm_alert", "verified": True,
        "entity_id": "contractor-1", "jurisdiction": "TX",
        "source_url": "https://api.weather.gov/alerts/active",
        "observed_at": TODAY.isoformat()
    }]}, as_of=TODAY)
    assert r["summary"]["signals_context_only"] == 1
    assert r["research_queue"][0]["research_priority"] == 5
    assert r["research_queue"][0]["review_state"] == "RESEARCH_ONLY"


def test_missing_demand_and_capacity_cannot_form_match():
    r = build_snapshot({"candidates": [
        sample(), sample("managed_repair_network", "network-1")
    ], "demands": [{"contractor_id": "contractor-1", "buyer_id": "network-1",
                     "jurisdiction": "TX", "service": "roofing",
                     "capacity_remaining": 0}]}, as_of=TODAY)
    assert r["summary"]["matches_for_founder_review"] == 0


def test_valid_buyer_evidence_still_does_not_authorize_allocation():
    r = build_snapshot({"candidates": [
        sample(), sample("managed_repair_network", "network-1")
    ], "demands": [{"contractor_id": "contractor-1", "buyer_id": "network-1",
                     "jurisdiction": "TX", "service": "roofing",
                     "capacity_remaining": 4,
                     "demand_evidence_url": "https://example.org/demand",
                     "capacity_evidence_url": "https://example.org/capacity",
                     "demand_verified": True, "capacity_verified": True}]}, as_of=TODAY)
    assert r["summary"]["matches_for_founder_review"] == 1
    assert not r["buyer_matches"][0]["allocation_authorized"]


def test_identical_replay_digest():
    payload = {"candidates": [sample()], "signals": []}
    x = build_snapshot(payload, as_of=TODAY)
    y = build_snapshot(payload, as_of=TODAY)
    assert x == y


@pytest.mark.parametrize("field,items", [
    ("candidates", [{}] * 501),
    ("signals", [{}] * 1001),
    ("offers", [{}] * 101),
    ("demands", [{}] * 201),
])
def test_bounded_inputs(field, items):
    with pytest.raises(ValueError):
        build_snapshot({field: items}, as_of=TODAY)


def test_economics_scenario_not_revenue():
    r = b2b_scenario(contractor_subscribers=5, network_subscribers=2,
                     pilots_sold=3)
    assert r["monthly_recurring_scenario"] == "22500.00"
    assert r["one_time_pilot_scenario"] == "4500.00"
    assert r["realised_revenue"] == "0.00"


@pytest.mark.parametrize("bad", [True, -1, 1.5, "two"])
def test_invalid_customer_counts_blocked(bad):
    with pytest.raises(ValueError):
        b2b_scenario(contractor_subscribers=bad)

from empire_os.claims_exchange.adapters import (
    buyer_queue_candidates, dfw_storm_candidates, normalized_domain,
)


def test_import_existing_buyer_stays_neutral_and_unverified():
    rows, report = buyer_queue_candidates({
        "schema_version": "buyer-network-candidate-queue-v1",
        "authority": "OBSERVE",
        "candidates": [{"domain": "ExampleRoofing.com",
                        "verticals": ["roofing"], "status": "WATCH",
                        "email": "should-not-be-imported@example.org"}],
    })
    assert report["neutral_candidates"] == 1
    assert rows[0]["kind"] == "buyer_research_candidate"
    assert rows[0]["jurisdiction"] == "UNVERIFIED"
    assert rows[0]["services"] == [] and rows[0]["evidence"] == []
    assert "email" not in str(rows)
    assert candidate_readiness(rows[0], as_of=TODAY)["review_state"] == "RESEARCH_ONLY"


def test_buyer_import_refuses_wrong_schema():
    with pytest.raises(ValueError):
        buyer_queue_candidates({"schema_version": "other", "authority": "OBSERVE",
                                "candidates": []})


def test_storm_import_does_not_infer_live_storm_or_ready_contact():
    rows, meta = dfw_storm_candidates({
        "schema_version": "empire.revenue_strike.storm.v1",
        "market": "Dallas-Fort Worth, TX", "outbound_sent": False,
        "prospects": [{"business_name": "Example Roofer", "website": "https://roofer.example.org"}],
    })
    assert meta["neutral_candidates"] == 1
    assert rows[0]["evidence"] == []
    assert candidate_readiness(rows[0], as_of=TODAY)["review_state"] == "RESEARCH_ONLY"


def test_bad_urls_dropped_from_import():
    assert normalized_domain("https://user:pass@company.com") == ""
    assert normalized_domain("https://127.0.0.1") == ""
    assert normalized_domain("https://www.example.com/") == "example.com"


def test_cross_id_duplicate_domain_quarantined():
    a, b = sample(entity="a"), sample(entity="b")
    b["public_domain"] = a["public_domain"]
    r = build_snapshot({"candidates": [a, b]}, as_of=TODAY)
    assert r["summary"]["unique_candidates"] == 0
    assert r["summary"]["conflicting_identity_groups_quarantined"] == 2


def test_signal_without_binding_does_not_crash_or_promote():
    r = build_snapshot({"candidates": [sample()], "signals": [{
        "kind": "storm_alert", "verified": True,
        "source_url": "https://api.weather.gov/alerts/active",
        "observed_at": TODAY.isoformat(), "jurisdiction": "TX",
    }]}, as_of=TODAY)
    assert r["summary"]["signals_context_only"] == 1
    assert r["research_queue"][0]["context_score"] == 0


def test_external_company_site_cannot_prove_own_identity():
    c = sample()
    c["evidence"][0]["source_url"] = "https://impersonator.example.net/x"
    result = candidate_readiness(c, as_of=TODAY)
    assert "identity" in result["missing_evidence"]
    assert result["evidence"]["rejected_reasons"]["first_party_domain_mismatch"] == 1


def test_arbitrary_offer_terms_blocked():
    r = offer_compliance({"basis": "fixed_service", "jurisdiction": "FL",
                          "terms": "bonus linked to amount paid by insurer"})
    assert r["quote_state"] == "BLOCKED_UNREVIEWED_TERMS"
    assert r["quote_authorized"] is False

from empire_os.claims_exchange.adapters import official_network_research_candidates


def test_two_official_network_sites_not_buyers_or_capacity():
    rows = official_network_research_candidates()
    assert len(rows) == 2
    assert all(x["kind"] == "managed_repair_network" for x in rows)
    assert all({i["kind"] for i in r["evidence"]} == {"identity", "service"} for r in rows)
    result = build_snapshot({"candidates": rows}, as_of=TODAY)
    assert result["summary"]["founder_review_ready"] == 0
    assert result["summary"]["matches_for_founder_review"] == 0
    assert all("buyer_demand" in item["missing_evidence"] for item in result["research_queue"])


def test_historical_official_program_evidence_expires():
    row = official_network_research_candidates()[0]
    r = candidate_readiness(row, as_of=date(2027, 3, 1))
    assert "identity" in r["missing_evidence"]
    assert "stale_or_future_evidence" in r["evidence"]["rejected_reasons"]


def test_revenue_first_triage_order_is_not_outbound_authority():
    dfw, _ = dfw_storm_candidates({
        "schema_version": "empire.revenue_strike.storm.v1",
        "market": "Dallas-Fort Worth, TX", "outbound_sent": False,
        "prospects": [{"business_name": "DFW Roofer", "website": "https://dfwroofs.org"}],
    })
    buyer, _ = buyer_queue_candidates({
        "schema_version": "buyer-network-candidate-queue-v1",
        "authority": "OBSERVE",
        "candidates": [{"domain": "buyer-network.org", "status": "VERIFY_REQUIREMENTS",
                        "verticals": ["roofing"]}],
    })
    pipeline = build_snapshot({"candidates": buyer + dfw + official_network_research_candidates()}, as_of=TODAY)
    lanes = [r["research_source"] for r in pipeline["research_queue"]]
    assert lanes == ["dfw_storm_cohort", "official_network_program",
                     "official_network_program", "buyer_network"]
    assert all(not row["outbound_authorized"] for row in pipeline["research_queue"])
