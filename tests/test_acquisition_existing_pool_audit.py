from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import io
import pytest

from empire_os.acquisition_existing_pool_audit import (
    audit_existing_acquisition_sources, load_committed_yc_pool
)


def records():
    return [{
        "yc_profile": "https://www.ycombinator.com/companies/example",
        "region": "US", "research_segment": "Marketing & Growth",
        "verification_status": "public_directory_only",
        "buyer_intent": "UNVERIFIED", "approval_state": "RESEARCH_ONLY",
    }]


def owner_snapshot():
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    stamp = now.isoformat()
    gtm = {
        "schema_version": "empire.gtm.integration_observer.v1",
        "generated_at": stamp, "radar_evidence_current": True,
        "mode": "OBSERVE", "authority": "none", "execution_authority": "none",
        "outreach_sent": False, "crm_write_performed": False,
        "handoffs": [{
            "source": "market_sweeps_revenue_gps", "opportunity_key": "test-1",
            "product_key": None, "status": "INTERNAL_RESEARCH_REVIEW_ONLY",
            "buyer_identity_verified": False, "outbound_authorized": False,
        }]
    }
    radar = {
        "schema_version": "empire.predictive_cloud.opportunity_radar.v1",
        "generated_at": stamp, "mode": "OBSERVE", "execution_authority": "none",
        "candidates": [{
            "opportunity_key": "test-1", "source": "market_sweeps_revenue_gps",
            "niche": "roofing", "offer_key": None,
            "buyer_intent_inferred": False, "commercial_demand_observed": False,
        }]
    }
    return gtm, radar, now


def test_research_first_pass_and_real_gtm_correlates():
    g, r, now = owner_snapshot()
    out = audit_existing_acquisition_sources(
        yc_rows=records(), yc_sha256="a" * 64, gtm=g, radar=r, now=now)
    assert out["yc_directory_records"] == 1
    assert out["yc_qualified_for_review"] == 0
    assert out["gtm_radar_correlated_handoffs"] == 1
    assert out["gtm_niche_counts"] == {"roofing": 1}
    assert out["gtm_product_counts"] == {"unclassified": 1}
    assert out["verified_revenue"] is None
    assert not out["outbound_authorized"] and not out["model_training_authorized"]


def test_rejects_expired_owner_snapshot():
    g, r, now = owner_snapshot()
    g["generated_at"] = "2026-10-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        audit_existing_acquisition_sources(
            yc_rows=records(), yc_sha256="a"*64, gtm=g, radar=r, now=now)


def test_rejects_unexpected_commercial_promotion_in_csv():
    g, r, now = owner_snapshot()
    rows = records()
    rows[0]["buyer_intent"] = "CONFIRMED"
    with pytest.raises(ValueError):
        audit_existing_acquisition_sources(
            yc_rows=rows, yc_sha256="a"*64, gtm=g, radar=r, now=now)


def test_repo_pinned_yc_source_exists_and_is_bounded():
    repo = Path(__file__).resolve().parents[1]
    rows, digest = load_committed_yc_pool(repo)
    assert len(rows) == 500
    assert len(digest) == 64
    assert all(row["approval_state"] == "RESEARCH_ONLY" for row in rows)


def test_research_batch_uses_actual_source_not_claimed_buyer_intent():
    g, r, now = owner_snapshot()
    item = records()[0]
    item["company"] = "Example Company"
    item["research_priority_score"] = "99"
    item["next_evidence"] = "Check original job posting"
    out = audit_existing_acquisition_sources(
        yc_rows=[item], yc_sha256="a"*64, gtm=g, radar=r, now=now)
    task = out["next_research_batch"][0]
    assert task["company"] == "Example Company"
    assert task["evidence_to_verify"] == "Check original job posting"
    assert task["product_code"] == "unclassified"
    assert task["status"] == "RESEARCH_ONLY"
    assert task["contact_authorized"] is False
