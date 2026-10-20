"""Synthetic contract tests for dry-run owner Revenue Distribution."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.commercial_distribution_shadow_refresh import (
    shadow_distribution_refresh_review,
)
from empire_os.revenue_distribution import SOURCES

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
FRESH = "2026-10-20T08:00:00Z"
OLD = "2026-09-29T08:00:00Z"


def _inputs(*, all_fresh=False, activated=0):
    values = {
        name: {
            "generated_at": (
                OLD if name in ("search", "competitor") and not all_fresh
                else FRESH
            ),
            "status": "OBSERVE",
        }
        for name in SOURCES
    }
    values["catalog"]["products"] = []
    values["radar"]["candidates"] = []
    values["buyer_scout"]["candidates"] = []
    values["buyer_capacity"].update({
        "buyers_seen": 4,
        "fully_activated": activated,
        "capacity_verified": 0,
        "terms_verified": 0,
    })
    return {
        "source_snapshots": values,
        "previous_distribution": {
            "schema_version": "empire.revenue_distribution.v1",
            "execution_authority": "none",
            "opportunities": [{"opportunity_key": "historical:1"}],
        },
        "now": NOW,
    }


def test_stale_sources_are_held_without_republishing():
    args = _inputs()
    before = deepcopy(args)
    out = shadow_distribution_refresh_review(**args)
    assert args == before
    assert out["source_count"] == len(SOURCES)
    assert out["source_state_counts"]["stale"] == 2
    assert out["source_state_counts"]["available"] == len(SOURCES)-2
    assert out["status"] == "SOURCE_AND_BUYER_EVIDENCE_HOLD"
    assert [a["source"] for a in out["source_owner_review_holds"]] == ["search", "competitor"]
    assert out["previous_stored_research_opportunity_count"] == 1
    assert out["shadow_research_opportunity_count"] == 0
    assert out["difference_is_not_verified_new_business"] is True
    assert out["snapshot_writes"] is False
    assert out["database_writes"] is False
    assert out["live_outbound_authorized"] is False
    assert out["agent_tasks_created"] is False


def test_fresh_inputs_without_activated_buyer_remain_held():
    out = shadow_distribution_refresh_review(**_inputs(all_fresh=True))
    assert out["source_state_counts"] == {"available": len(SOURCES)}
    assert out["status"] == "BUYER_EVIDENCE_HOLD"
    assert out["source_owner_review_holds"] == []
    assert out["buyer_capacity_source_counts_not_buyer_demand_proof"]["fully_activated"] == 0


def test_activated_buyer_claim_still_no_send_authority():
    out = shadow_distribution_refresh_review(**_inputs(all_fresh=True, activated=1))
    assert out["status"] == "DISTRIBUTION_SHADOW_REVIEW_ONLY"
    assert out["payment_authorized"] is False
    assert out["paid_ad_spend_authorized"] is False
    assert out["execution_authority"] == "none"


def test_unknown_input_clock_is_not_refreshed_automatically():
    args = _inputs()
    args["source_snapshots"]["search"].pop("generated_at")
    out = shadow_distribution_refresh_review(**args)
    assert out["source_states"]["search"] == "unknown_freshness"
    assert out["source_evidence_review_required"] is True


def test_invalid_source_population_fails_closed():
    args = _inputs()
    del args["source_snapshots"]["search"]
    with pytest.raises(ValueError, match="exact existing"):
        shadow_distribution_refresh_review(**args)


def test_previous_distribution_must_have_correct_schema():
    args = _inputs()
    args["previous_distribution"]["schema_version"] = "fraud"
    with pytest.raises(ValueError, match="prior canonical"):
        shadow_distribution_refresh_review(**args)


def test_previous_distribution_cannot_claim_execution_authority():
    args = _inputs()
    args["previous_distribution"]["execution_authority"] = "SEND"
    with pytest.raises(ValueError, match="non-executing"):
        shadow_distribution_refresh_review(**args)


def test_untrusted_previous_opportunity_list_rejected():
    args = _inputs()
    args["previous_distribution"]["opportunities"] = "unbounded"
    with pytest.raises(ValueError, match="bounded"):
        shadow_distribution_refresh_review(**args)


def test_naive_clock_rejected():
    args = _inputs()
    args["now"] = datetime(2026, 10, 20, 9)
    with pytest.raises(ValueError, match="timezone-aware"):
        shadow_distribution_refresh_review(**args)


def test_source_unavailability_is_an_explicit_hold():
    args = _inputs(all_fresh=True)
    args["source_snapshots"]["conversion"] = None
    out = shadow_distribution_refresh_review(**args)
    assert out["source_states"]["conversion"] == "missing_or_invalid"
    assert "conversion_intelligence_owner" in [x["existing_owner_lane"] for x in out["source_owner_review_holds"]]
