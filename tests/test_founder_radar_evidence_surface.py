"""Existing Founder Radar surface: current Router evidence, no authority promotion."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

import pytest

from empire_os.founder_dashboard import _radar_lifecycle_evidence, build_founder_dashboard

START = "2026-10-11T17:00:00+00:00"
ROUTED = "2026-10-11T17:01:07+00:00"
END = "2026-10-11T17:01:09+00:00"
KEY = "market:roofing:denver"


def loop():
    return {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v2",
        "mode": "OBSERVE", "ok": True, "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "started_at": START, "finished_at": END,
        "radar_candidate_count": 1, "opportunity_stage_counts": {"QUALIFY": 1},
    }


def routes(history=False):
    data = {
        "schema_version": "empire.opportunity_evidence_routes.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "generated_at": ROUTED,
        "opportunity_count": 1, "stage_counts": {"QUALIFY": 1},
        "items": [{
            "opportunity_key": KEY,
            "opportunity_class": "market_research",
            "tenant_id": None,
            "lifecycle": {"current_stage": "QUALIFY"},
        }],
    }
    if history:
        data["history"] = {
            "schema_version": "empire.opportunity_evidence_history.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "automatic_external_execution_allowed": False,
            "commercial_stage_independently_verified": False,
            "previous_stage_never_promoted": True,
            "generated_at": ROUTED,
            "tracked_identity_count": 1,
            "new_identity_count": 0, "reappeared_count": 0,
            "stage_transition_count_this_cycle": 0,
            "entries": [{
                "opportunity_key": KEY, "opportunity_class": "market_research",
                "tenant_id": None, "active_in_latest_cycle": True,
                "missed_cycles": 0, "last_observed_stage": "QUALIFY",
                "stage_source": "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF",
                "last_seen_at": ROUTED, "execution_authority": "none",
            }],
        }
    return data


def test_router_without_live_history_is_not_claimed_new_or_advanced():
    x = _radar_lifecycle_evidence(loop(), routes())
    assert x["status"] == "CURRENT_ROUTER_WITHOUT_HISTORY"
    assert x["router_stage_counts"] == {"QUALIFY": 1}
    assert x["new_identity_count_latest_cycle"] is None
    assert x["derived_stage_transitions_latest_cycle"] is None
    assert x["commercial_validation_verified"] is False
    assert x["outreach_authorized"] is False
    assert x["execution_authority"] == "none"


def test_same_cycle_verified_observed_history_is_projection_not_revenue():
    l, r = loop(), routes(True)
    original = deepcopy((l, r))
    x = _radar_lifecycle_evidence(l, r)
    assert x["status"] == "CURRENT_DERIVED_HISTORY_OBSERVED"
    assert x["new_identity_count_latest_cycle"] == 0
    assert x["derived_stage_transitions_latest_cycle"] == 0
    assert x["history_verified_for_cycle"] is True
    assert x["commercial_validation_verified"] is False
    assert (l, r) == original


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", "unknown"),
    ("mode", "EXECUTE"),
    ("execution_authority", "LIVE_TRAFFIC"),
    ("automatic_external_execution_allowed", True),
    ("generated_at", "2026-10-10T17:01:07+00:00"),
    ("generated_at", "2026-10-11T19:01:07+00:00"),
    ("opportunity_count", 12),
    ("opportunity_count", True),
    ("stage_counts", {"VALIDATE": 1}),
])
def test_wrong_router_identity_or_cycle_is_held(field, value):
    r = routes(True)
    r[field] = value
    x = _radar_lifecycle_evidence(loop(), r)
    assert x["status"] == "UNKNOWN_SOURCE_UNVERIFIED"
    assert x["derived_stage_transitions_latest_cycle"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", "wrong"),
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("automatic_external_execution_allowed", True),
    ("commercial_stage_independently_verified", True),
    ("previous_stage_never_promoted", False),
    ("generated_at", "2026-10-10T17:01:07+00:00"),
    ("new_identity_count", "1"),
    ("stage_transition_count_this_cycle", True),
])
def test_history_forgery_never_claims_promotion(field, value):
    r = routes(True)
    r["history"][field] = value
    x = _radar_lifecycle_evidence(loop(), r)
    assert x["history_verified_for_cycle"] is False
    assert x["derived_stage_transitions_latest_cycle"] is None
    assert x["commercial_validation_verified"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("tenant_id", "tenant:wrong"),
    ("opportunity_class", "tam"),
    ("missed_cycles", 1),
    ("last_observed_stage", "PROVE"),
    ("execution_authority", "live"),
    ("last_seen_at", "2026-10-10T17:01:07+00:00"),
])
def test_history_cross_scope_or_stale_row_rejected(field, value):
    r = routes(True)
    r["history"]["entries"][0][field] = value
    x = _radar_lifecycle_evidence(loop(), r)
    assert x["status"] == "CURRENT_ROUTER_WITHOUT_HISTORY"
    assert x["history_verified_for_cycle"] is False


def test_router_duplicate_and_invalid_counts_are_not_trusted():
    r = routes()
    r["items"] = [r["items"][0], deepcopy(r["items"][0])]
    r["opportunity_count"] = 2
    r["stage_counts"] = {"QUALIFY": 2}
    x = _radar_lifecycle_evidence(loop(), r)
    assert x["status"] == "UNKNOWN_SOURCE_UNVERIFIED"


def test_no_loop_or_router_keeps_unknown():
    for left,right in ((None, None), (loop(), None), (None, routes())):
        x = _radar_lifecycle_evidence(left, right)
        assert x["status"] == "UNKNOWN_SOURCE_UNVERIFIED"
        assert x["new_identity_count_latest_cycle"] is None


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_existing_founder_dashboard_now_exposes_router_lifecycle_without_new_api(tmp_path):
    root=tmp_path
    dump(root / "runtime/opportunity_radar/loop_latest.json", loop())
    dump(root / "runtime/opportunity_factory/intake_latest.json", {
        "items": [{
            "opportunity_key": KEY,
            "factory_ready": False,
            "blockers": ["independent_buyer_intent_missing"],
        }]
    })
    dump(root / "runtime/opportunity_factory/evidence_routes_latest.json", routes(True))
    before={
        str(p):p.read_bytes()
        for p in (root/"runtime").rglob("*.json")
    }
    snapshot=build_founder_dashboard(root)
    radar=snapshot["opportunity_radar"]
    assert radar["lifecycle_evidence"]["history_verified_for_cycle"] is True
    assert radar["lifecycle_evidence"]["commercial_validation_verified"] is False
    assert radar["blocker_counts"]["independent_buyer_intent_missing"] == 1
    assert snapshot["execution_authority"] == "none"
    assert before=={str(p):p.read_bytes() for p in (root/"runtime").rglob("*.json")}
