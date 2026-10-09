from empire_os.claims_exchange import (
    assess_candidate, assess_offer, build_review_packets, match_capacity
)


def candidate(kind="contractor", company="acme", jurisdiction="TX", full=True):
    base = ["identity", "service", "territory", "public_contact_route"]
    if kind == "licensed_claims_partner":
        base.append("licensed_status")
    if kind in {"carrier", "managed_repair_network"}:
        base.extend(["buyer_demand", "buyer_capacity"])
    return {
        "entity_id": company, "kind": kind, "jurisdiction": jurisdiction,
        "services": ["roofing"],
        "evidence": [
            {"kind": typ, "source_url": "https://example.org/a",
             "observed_at": "2026-10-09", "verified": full}
            for typ in base
        ],
    }


def test_missing_provenance_stays_research_only():
    row = assess_candidate(candidate(full=False))
    assert row["review_state"] == "RESEARCH_READY"
    assert row["outbound_authorized"] is False


def test_verified_b2b_candidate_remains_founder_gated():
    row = assess_candidate(candidate())
    assert row["review_state"] == "FOUNDER_REVIEW_READY"
    assert row["execution_authority"] == "none"
    assert row["contract_authorized"] is False


def test_claims_partner_requires_license_evidence():
    row = candidate("licensed_claims_partner")
    row["evidence"] = [e for e in row["evidence"] if e["kind"] != "licensed_status"]
    assert "licensed_status" in assess_candidate(row)["missing_evidence"]


def test_settlement_commission_never_automatically_allowed_even_in_florida():
    for state in ("FL", "TX", "UK"):
        r = assess_offer({"basis": "settlement_percentage", "jurisdiction": state,
                          "proposed_rate": 99, "licensed": True})
        assert not r["settlement_fee_authorized"]
        assert r["quote_state"] == "BLOCKED_PENDING_SPECIALIST_LEGAL_REVIEW"


def test_standard_subscription_only_allowed_as_draft():
    result = assess_offer({"basis": "subscription", "jurisdiction": "TX"})
    assert result["quote_state"] == "FOUNDER_TERMS_REVIEW"
    assert not result["quote_authorized"]


def test_claim_referral_requires_review():
    for basis in ("claim_referral", "repair_contract_percentage",
                  "claim_qualified_opportunity", "qualified_opportunity"):
        result = assess_offer({"basis": basis, "jurisdiction": "FL"})
        assert result["quote_state"].startswith("BLOCKED")
        assert not result["outbound_authorized"]


def test_demand_and_capacity_required_to_suggest_matching():
    c, b = candidate(), candidate("managed_repair_network", "network")
    evidence = {"service": "roofing", "capacity_remaining": 3,
                "demand_evidence_url": "https://example.org/demand",
                "capacity_evidence_url": "https://example.org/capacity",
                "demand_verified": True, "capacity_verified": True}
    good = match_capacity(c, b, evidence)
    assert good["state"] == "MATCH_FOR_FOUNDER_REVIEW"
    assert good["allocation_authorized"] is False
    assert good["outbound_authorized"] is False
    evidence["capacity_remaining"] = 0
    assert match_capacity(c, b, evidence)["state"] == "RESEARCH_ONLY"


def test_cross_territory_and_unproved_demand_never_match():
    c, b = candidate(), candidate("carrier", "network", jurisdiction="FL")
    r = match_capacity(c, b, {"service": "roofing", "capacity_remaining": 20})
    assert "territory_mismatch" in r["reasons"]
    assert r["state"] == "RESEARCH_ONLY"


def test_dedupe_by_canonical_id_and_jurisdiction():
    rows = build_review_packets([candidate(), candidate(), candidate(jurisdiction="FL")])
    assert len(rows) == 2
    assert all(x["execution_authority"] == "none" for x in rows)


def test_bad_provenance_urls_do_not_verify():
    row = candidate()
    row["evidence"][0]["source_url"] = "http://example.org/insecure"
    assert "identity" in assess_candidate(row)["missing_evidence"]
