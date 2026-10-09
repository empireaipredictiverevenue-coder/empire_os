
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.opportunity_source_convergence import (
    idle_asset_candidates,
    predictive_cloud_gap_candidates,
)


def stamp(hours=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def report(records, category="unsaturated", tenant="tenant-a", hours=0):
    family = "market_gaps" if category in ("hot_gaps", "unsaturated") else "waste"
    return {
        "schema_version": "predictive_cloud.v2",
        "tenant_id": tenant,
        "timestamp": stamp(hours),
        "intelligence": {family: {category: records}},
    }


def adapt(payload):
    return predictive_cloud_gap_candidates(
        payload,
        tenant_id="tenant-a",
        evidence_ref="test:canonical_report",
    )


@pytest.mark.parametrize("occupancy", [
    None, True, False, -0.1, 1.1,
    float("nan"), float("inf"), "0.5",
])
def test_invalid_occupancy_rejected(occupancy):
    assert adapt(report([{
        "niche_metro": "roofing:denver",
        "occupancy": occupancy,
        "leads": 8,
    }])) == []


@pytest.mark.parametrize("leads", [
    None, True, False, -1, 1.5,
    float("nan"), "8",
])
def test_invalid_leads_rejected(leads):
    assert adapt(report([{
        "niche_metro": "roofing:denver",
        "occupancy": 0.2,
        "leads": leads,
    }])) == []


def test_duplicate_market_gap_identity_rejected():
    item = {
        "niche_metro": "roofing:denver",
        "occupancy": 0.2,
        "leads": 8,
    }
    assert len(adapt(report([item, dict(item)]))) == 1


def test_cross_tenant_report_rejected():
    assert adapt(report([{
        "niche_metro": "roofing:denver",
        "occupancy": 0.2,
        "leads": 8,
    }], tenant="tenant-b")) == []


def test_stale_report_rejected():
    assert adapt(report([{
        "niche_metro": "roofing:denver",
        "occupancy": 0.2,
        "leads": 8,
    }], hours=48)) == []


@pytest.mark.parametrize("category,identity", [
    ("waste_lanes", "lane_id"),
    ("waste_agents", "agent"),
    ("waste_hotspots", "scope"),
])
def test_waste_identity_and_dedup(category, identity):
    row = {identity: "observed-1"}
    rows = adapt(report([row, dict(row)], category=category))
    assert len(rows) == 1
    assert rows[0]["source_kind"] == "idle_waste"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["opportunity_factory_ready"] is False


def test_missing_waste_identity_rejected():
    assert adapt(report([{"issue": "missing"}], category="waste_agents")) == []


def test_candidate_has_no_commercial_authority():
    rows = adapt(report([{
        "niche_metro": "roofing:denver",
        "occupancy": 0.2,
        "leads": 8,
    }]))
    assert len(rows) == 1
    for field in (
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert rows[0][field] == "none"
    assert rows[0]["recognized_revenue_cents"] is None


def test_idle_asset_invalid_and_duplicate():
    rows = idle_asset_candidates(
        [
            {
                "tenant_id": "tenant-a",
                "observed_at": stamp(),
                "compound_id": "asset-1",
                "lead_gen_score": 0.8,
            },
            {
                "tenant_id": "tenant-a",
                "observed_at": stamp(),
                "compound_id": "asset-1",
                "lead_gen_score": 0.8,
            },
        ],
        tenant_id="tenant-a",
        evidence_scope="canonical",
    )
    assert len(rows) == 1
    assert rows[0]["opportunity_factory_ready"] is False
