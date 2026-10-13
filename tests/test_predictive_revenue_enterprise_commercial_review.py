"""Review-only qualified evidence, never unreviewed commercial activation."""
import json
import stat

import pytest

from empire_os.predictive_revenue_enterprise_commercial_review import build_review
from scripts.build_predictive_revenue_enterprise_commercial_review import run


def fixtures():
    candidate = {
        "domain": "example.com", "candidate_id": "current-id",
        "account_name": "Example Industries", "website": "https://example.com/",
        "target_product_codes": ["predictive_revenue_diagnostic"],
        "commercial_readiness": {"state": "FIT_REVIEW", "first_party_person_observed": True},
    }
    place = dict(candidate, location_verified=True, site_probe_ok=True,
                 location_source="first_party_site_address",
                 metro="Austin, TX", location_evidence_addresses=["Austin, TX 78701"])
    pool = {"mode": "OBSERVE", "outreach_authorized": False,
            "rolling_candidates": [candidate]}
    locations = {"mode": "OBSERVE", "outreach_authorized": False,
                 "candidates": [place]}
    promotion = {"mode": "OBSERVE", "outbound_sent": False,
                 "proposals": [{"domain": "example.com", "candidate_id": "current-id",
                                "source_prospect_ids": []}]}
    return pool, locations, promotion


def test_fit_review_packet_preserves_all_commercial_gates():
    out = build_review(*fixtures(), generated_at="2026-10-13T22:00:00+00:00")
    assert out["location_verified_current_count"] == 1
    assert out["fit_review_current_count"] == 1
    assert out["commercially_qualified_count"] == 0
    assert out["outreach_authorized"] is False
    assert out["database_write_performed"] is False
    packet = out["packets"][0]
    assert packet["fit_state"] == "FIT_REVIEW"
    assert packet["verified_buying_intent"] is False
    assert packet["person_email_binding_verified"] is False
    assert packet["prior_contact_status"] == "UNKNOWN_RECHECK_REQUIRED"
    assert packet["suppression_status"] == "UNKNOWN_SEND_TIME_CHECK_REQUIRED"
    assert "CANONICAL_PROSPECT_LINK_UNAVAILABLE" in packet["blockers"]


def test_stale_location_and_removed_pool_candidates_do_not_enter_review():
    pool, locations, promotion = fixtures()
    locations["candidates"][0]["candidate_id"] = "stale-id"
    assert build_review(pool, locations, promotion)["packets"] == []
    locations["candidates"][0]["candidate_id"] = "current-id"
    pool["rolling_candidates"] = []
    assert build_review(pool, locations, promotion)["packets"] == []


def test_location_requires_matching_first_party_probe_and_address():
    pool, locations, promotion = fixtures()
    locations["candidates"][0]["site_probe_ok"] = False
    assert build_review(pool, locations, promotion)["packets"] == []
    locations["candidates"][0]["site_probe_ok"] = True
    locations["candidates"][0]["location_evidence_addresses"] = ["Paris, France"]
    assert build_review(pool, locations, promotion)["packets"] == []


def test_absent_product_or_person_keeps_research_only():
    pool, locations, promotion = fixtures()
    pool["rolling_candidates"][0]["target_product_codes"] = []
    pool["rolling_candidates"][0]["commercial_readiness"] = {
        "state": "RESEARCH_ONLY", "first_party_person_observed": False,
    }
    out = build_review(pool, locations, promotion)
    assert out["fit_review_current_count"] == 0
    assert out["packets"][0]["fit_state"] == "RESEARCH_ONLY"
    assert "PRODUCT_OR_FIRST_PARTY_PERSON_REVIEW_REQUIRED" in out["packets"][0]["blockers"]


def test_untrusted_source_modes_fail_closed():
    pool, locations, promotion = fixtures()
    promotion["outbound_sent"] = True
    with pytest.raises(ValueError, match="UNTRUSTED_ENTERPRISE_REVIEW_SOURCES"):
        build_review(pool, locations, promotion)


def test_script_writes_private_review_snapshot_without_side_effects(tmp_path):
    pool, locations, promotion = fixtures()
    files = {
        "runtime/predictive_revenue/enterprise_pool_latest.json": pool,
        "runtime/predictive_revenue/enterprise_location_enrichment_latest.json": locations,
        "runtime/buyer_acquisition/promotion_plan_latest.json": promotion,
    }
    for name, data in files.items():
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data))
    out = run(tmp_path)
    path = tmp_path / "runtime/predictive_revenue/enterprise_commercial_review_latest.json"
    assert out["location_verified_current_count"] == 1
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["outreach_authorized"] is False
