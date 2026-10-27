"""Public change briefs must not mutate existing lead/revenue or buyer decisions."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.competitor_change_radar import build_radar
from empire_os.competitor_opportunity_evidence_bridge import (
    SCHEMA, build_commercial_evidence_bridge, build_bridge_runtime,
)
from empire_os.competitor_intelligence_feed import build_feed_runtime

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def receipt(price, t=0, url="https://www.examplebuyers.com/pricing"):
    return {
        "entity_id": "operator-one",
        "company_name": "Example Buyers",
        "source_ref": url,
        "observed_at": (NOW + timedelta(minutes=t)).isoformat(),
        "fetch_authority": "PUBLIC_ROBOTS_PERMITTED",
        "html": ("<main><h1>Partner access</h1>"
                 f"<p>Pricing starts at £{price} per month for partner accounts.</p>"
                 "<p>New feature includes API access and automatic routing.</p></main>"),
        "industry": "services",
        "territory": "UK",
    }


def radar():
    first = build_radar([receipt(29)])
    return build_radar([receipt(39, 2)], previous=first)


def buyer(domain="examplebuyers.com"):
    return {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "mode": "OBSERVE", "execution_authority": "none", "outbound_sent": False,
        "candidates": [{
            "domain": domain, "candidate_state": "RESEARCH_EVIDENCE_ONLY",
            "canonical_identity_verified": False,
            "commercial_terms_verified": False,
            "budget_verified": False,
            "first_party_emails": ["do-not-export@examplebuyers.com"],
        }],
    }


def briefs(domain="examplebuyers.com"):
    return {
        "mode": "REVIEW_ONLY", "execution_authority": "none",
        "external_send_allowed": False, "briefs": [{
            "company_website": "https://www." + domain,
            "review_ready": True, "entity_id": "account-1",
        }],
    }


def test_real_change_creates_review_only_evidence_with_source_and_proofs():
    result = build_commercial_evidence_bridge(radar(), buyer_scout=buyer(),
                                               opportunity_briefs=briefs(), now=NOW+timedelta(minutes=5))
    assert result["schema_version"] == SCHEMA
    assert result["radar_pending_change_count"] == 1
    assert result["current_research_brief_count"] == 1
    assert result["exact_buyer_scout_domain_matches"] == 1
    assert result["exact_opportunity_brief_domain_matches"] == 1
    card = result["research_cards"][0]
    assert card["source_ref"] == "https://www.examplebuyers.com/pricing"
    assert card["buyer_scout_candidate_state"] == "RESEARCH_EVIDENCE_ONLY"
    assert card["commercial_readiness"] == "REQUIRES_INDEPENDENT_QUALIFICATION"
    assert card["fact_count"] >= 1
    assert "written_commercial_terms" in card["required_proofs"]
    assert card["task_dispatched"] is False
    assert card["outreach_authorized"] is False
    assert card["qualified_lead"] is False
    assert result["qualified_lead_count"] == 0
    assert result["verified_revenue"] is False
    assert "do-not-export" not in json.dumps(result)


def test_similar_domain_is_not_exact_buyer_match():
    result = build_commercial_evidence_bridge(
        radar(), buyer_scout=buyer("examplebuyers.co.uk"),
        opportunity_briefs=briefs("examplebuyers.co.uk"), now=NOW+timedelta(minutes=3))
    assert result["current_research_brief_count"] == 1
    assert result["exact_buyer_scout_domain_matches"] == 0
    assert result["exact_opportunity_brief_domain_matches"] == 0


def test_old_changes_cannot_be_called_current_opportunity():
    stale = build_commercial_evidence_bridge(radar(), now=NOW+timedelta(days=8))
    assert stale["radar_pending_change_count"] == 1
    assert stale["stale_reviews_not_actionable"] == 1
    assert stale["current_research_brief_count"] == 0


def test_baseline_and_unchanged_are_not_qualified_opportunities():
    base = build_radar([receipt(29)])
    result = build_commercial_evidence_bridge(base, now=NOW+timedelta(minutes=3))
    assert result["radar_observed_source_count"] == 1
    assert result["current_research_brief_count"] == 0
    assert result["buyer_admission_authorized"] is False


@pytest.mark.parametrize("change", [
    ("outreach_enabled", True),
    ("payment_authorized", True),
    ("verified_revenue", True),
    ("buyer_intent_inferred", True),
])
def test_unauthorised_radar_state_rejected(change):
    r = radar()
    r[change[0]] = change[1]
    with pytest.raises(ValueError, match="review-only"):
        build_commercial_evidence_bridge(r, now=NOW+timedelta(minutes=3))


def test_fake_change_without_original_baseline_rejected():
    r = radar()
    r["observations"] = []
    with pytest.raises(ValueError, match="canonical baseline"):
        build_commercial_evidence_bridge(r, now=NOW+timedelta(minutes=3))


def test_untrusted_scout_or_opportunity_batch_rejected():
    b = buyer()
    b["outbound_sent"] = True
    with pytest.raises(ValueError, match="buyer-scouter"):
        build_commercial_evidence_bridge(radar(), buyer_scout=b, now=NOW+timedelta(minutes=3))
    q = briefs()
    q["execution_authority"] = "send"
    with pytest.raises(ValueError, match="opportunity-brief"):
        build_commercial_evidence_bridge(radar(), opportunity_briefs=q, now=NOW+timedelta(minutes=3))


def test_existing_feed_reader_exposes_bridge_but_lead_count_unchanged(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    base = runtime / "competitive_intelligence"
    base.mkdir(parents=True)
    (base / "competitor_change_radar_latest.json").write_text(json.dumps(radar()))
    (base / "competitor_intelligence_feed_latest.json").write_text(json.dumps({
        "schema_version": "empire.competitor_intelligence_feed.v1",
        "mode": "OBSERVE", "canonical_company_count": 14,
        "outreach_enabled": False, "buyer_intent_inferred": False,
    }))
    buyer_root = runtime / "buyer_acquisition"
    buyer_root.mkdir()
    (buyer_root / "scout_latest.json").write_text(json.dumps(buyer()))
    from empire_os import competitor_opportunity_evidence_bridge as bridge
    monkeypatch.setattr(bridge, "MAX_AGE", timedelta(days=40000))
    feed = build_feed_runtime(tmp_path)
    assert feed["canonical_company_count"] == 14
    assert feed["commercial_opportunity_research"]["available"] is True
    assert feed["commercial_opportunity_research"]["current_research_brief_count"] == 1
    assert feed["commercial_opportunity_research"]["qualified_lead_count"] == 0
    assert feed["outreach_enabled"] is False


def test_no_snapshot_or_invalid_snapshot_fails_closed(tmp_path):
    assert build_bridge_runtime(tmp_path)["available"] is False
    base = tmp_path / "runtime/competitive_intelligence"
    base.mkdir(parents=True)
    (base / "competitor_change_radar_latest.json").write_text("{}")
    assert build_bridge_runtime(tmp_path)["available"] is False
