"""Research-only buyer intelligence cannot launder claims into verified tiers."""
import json

import pytest

from scripts.build_buyer_intelligence_reuse import build


def _source(tmp_path):
    base = tmp_path / "runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    obs = {
        "schema_version": "empire.targeted_evidence_observations.v1",
        "mode": "OBSERVE", "execution_authority": "none", "outbound_sent": False,
        "requirements": [{
            "domain": "buyer.example", "requirement": "verify_active_buyer_demand",
            "verified": False, "commercial_terms_approved": False,
            "outbound_authorized": False,
            "claim_leads": [{
                "url": "https://buyer.example/partners", "matched_phrase": "buy leads",
                "evidence_status": "UNVERIFIED_CLAIM_LEAD",
            }],
        }],
    }
    qualification = {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False, "outbound_enabled": False,
        "targets": [{
            "domain": "buyer.example", "founder_research_decision": "CONTINUE_RESEARCH",
            "verticals": ["home_services"], "missing_evidence": ["verify_active_buyer_demand"],
            # Forged truth-looking booleans must not promote a research-only prospect.
            "verified_evidence": {
                "company_identity_verified": True, "icp_match_verified": True,
                "demand_verified": True, "contact_path_verified": True,
                "commercial_terms_verified": True, "compliance_verified": True,
                "decision_maker_verified": True, "strategic_value_verified": True,
            },
            "verified_scoring_components": {
                "icp_fit": 100, "demand": 100, "potential_value": 100,
                "freshness": 100, "transaction_readiness": 100,
            },
        }],
    }
    (base / "targeted_evidence_observations_latest.json").write_text(json.dumps(obs))
    (base / "founder_qualification_actions_latest.json").write_text(json.dumps(qualification))
    return base, obs, qualification


def test_research_claims_never_promote_premium_or_executive(tmp_path):
    base, _, _ = _source(tmp_path)
    report = build(base)
    buyer = report["buyers"][0]
    assert buyer["qualification_tier"] == "BASIC"
    assert buyer["lead_intelligence_formula"]["opportunity_score"] is None
    assert buyer["lead_intelligence_formula"]["evidence_confidence_score"] == 0
    assert buyer["qualified_buyer"] is False
    assert buyer["outbound_authorized"] is False
    assert buyer["commercial_activation_decision"] == "BLOCK"


@pytest.mark.parametrize("url", [
    "https://buyer.example.evil.test/partners",
    "https://buyer.example@evil.test/partners",
    "http://buyer.example/partners",
])
def test_spoofed_first_party_claim_url_rejected(tmp_path, url):
    base, obs, _ = _source(tmp_path)
    obs["requirements"][0]["claim_leads"][0]["url"] = url
    (base / "targeted_evidence_observations_latest.json").write_text(json.dumps(obs))
    with pytest.raises(ValueError, match="non_first_party"):
        build(base)


def test_buyer_claim_cannot_override_commercial_terms_gate(tmp_path):
    base, obs, _ = _source(tmp_path)
    obs["requirements"][0]["commercial_terms_approved"] = True
    (base / "targeted_evidence_observations_latest.json").write_text(json.dumps(obs))
    with pytest.raises(ValueError, match="unsafe_observation_row"):
        build(base)


def test_outbound_ready_qualification_snapshot_rejected(tmp_path):
    base, _, qualification = _source(tmp_path)
    qualification["outbound_enabled"] = True
    (base / "founder_qualification_actions_latest.json").write_text(json.dumps(qualification))
    with pytest.raises(ValueError, match="unsafe_qualification_snapshot"):
        build(base)
