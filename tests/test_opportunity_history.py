"""Cycle-stable lifecycle history in the existing Evidence Router artifact."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.opportunity_history import build_opportunity_history, SCHEMA
from empire_os.opportunity_evidence_router import (
    build_evidence_routes, refresh_evidence_routes, OUTPUT, RADAR, INTAKE,
)

UTC = timezone.utc
T1 = "2026-10-11T10:00:00+00:00"
T2 = "2026-10-11T10:30:00+00:00"
T3 = "2026-10-11T11:00:00+00:00"
T4 = "2026-10-11T11:30:00+00:00"


def item(key="market:roofing:denver", stage="DISCOVER", *,
         klass="market_research", tenant=None):
    return {
        "opportunity_key": key, "opportunity_class": klass,
        "tenant_id": tenant, "lifecycle": {"current_stage": stage},
        "routes": [], "execution_authority": "none",
    }


def routes(when=T1, items=None):
    values = [item()] if items is None else items
    return {
        "schema_version": "empire.opportunity_evidence_routes.v1",
        "mode": "OBSERVE",
        "generated_at": when,
        "items": values,
        "opportunity_count": len(values),
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def keyed(history, key="market:roofing:denver"):
    return next(row for row in history["entries"] if row["opportunity_key"] == key)


def test_first_cycle_keeps_no_commercial_or_execution_authority():
    out = build_opportunity_history(routes())
    assert out["schema_version"] == SCHEMA
    assert out["previous_source_status"] == "INITIAL"
    assert out["tracked_identity_count"] == 1
    assert out["new_identity_count"] == 1
    assert out["active_identity_count"] == 1
    assert out["stage_counts_current"] == {"DISCOVER": 1}
    assert out["commercial_stage_independently_verified"] is False
    assert out["previous_stage_never_promoted"] is True
    assert out["automatic_external_execution_allowed"] is False
    assert out["execution_authority"] == "none"
    row = out["entries"][0]
    assert row["first_seen_at"] == row["last_seen_at"] == T1
    assert row["observation_count"] == 1
    assert row["stage_source"] == "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF"
    assert row["stage_transition_count"] == 0


def test_second_cycle_tracks_same_identity_without_inventing_new_lead():
    first = routes()
    first["history"] = build_opportunity_history(first)
    second = build_opportunity_history(routes(T2), first)
    row = keyed(second)
    assert second["previous_source_status"] == "CONTINUING"
    assert second["new_identity_count"] == 0
    assert second["tracked_identity_count"] == 1
    assert row["first_seen_at"] == T1
    assert row["last_seen_at"] == T2
    assert row["observation_count"] == 2
    assert row["stage_transition_count"] == 0


def test_duplicate_identity_within_same_cycle_fails_closed():
    duplicated = routes(items=[item(), item(stage="QUALIFY")])
    with pytest.raises(ValueError, match="HISTORY_DUPLICATE_CURRENT_KEY"):
        build_opportunity_history(duplicated)


def test_opportunity_disappearance_is_not_retirement_or_verified_revenue():
    previous = routes()
    previous["history"] = build_opportunity_history(previous)
    missing = build_opportunity_history(routes(T2, []), previous)
    assert missing["new_identity_count"] == 0
    assert missing["not_observed_in_latest_cycle_count"] == 1
    assert missing["stage_counts_current"] == {}
    retained = keyed(missing)
    assert retained["first_seen_at"] == T1
    assert retained["last_seen_at"] == T1
    assert retained["missed_cycles"] == 1
    assert retained["active_in_latest_cycle"] is False
    assert retained["last_observed_stage"] == "DISCOVER"

    second_routes = routes(T2, [])
    second_routes["history"] = missing
    third = build_opportunity_history(routes(T3, []), second_routes)
    assert keyed(third)["missed_cycles"] == 2
    assert keyed(third)["last_seen_at"] == T1


def test_reappearance_preserves_first_seen_and_counts_one_reappearance():
    baseline = routes()
    baseline["history"] = build_opportunity_history(baseline)
    gap = routes(T2, [])
    gap["history"] = build_opportunity_history(gap, baseline)
    recovered = build_opportunity_history(routes(T3), gap)
    assert recovered["reappeared_count"] == 1
    assert recovered["new_identity_count"] == 0
    assert keyed(recovered)["observation_count"] == 2
    assert keyed(recovered)["missed_cycles"] == 0
    assert keyed(recovered)["first_seen_at"] == T1


def test_stage_regression_retained_instead_of_illegal_promotion():
    earlier = routes(items=[item(stage="VALIDATE")])
    earlier["history"] = build_opportunity_history(earlier)
    later = build_opportunity_history(routes(T2, [item(stage="QUALIFY")]), earlier)
    assert later["stage_transition_count_this_cycle"] == 1
    assert keyed(later)["last_observed_stage"] == "QUALIFY"
    assert keyed(later)["stage_transition_count"] == 1
    assert later["stage_counts_current"] == {"QUALIFY": 1}
    assert later["previous_stage_never_promoted"] is True


def test_stage_progression_is_observed_not_independently_verified():
    previous = routes()
    previous["history"] = build_opportunity_history(previous)
    out = build_opportunity_history(routes(T2, [item(stage="PROVE")]), previous)
    assert keyed(out)["last_observed_stage"] == "PROVE"
    assert keyed(out)["stage_transition_count"] == 1
    assert out["commercial_stage_independently_verified"] is False
    assert out["execution_authority"] == "none"


@pytest.mark.parametrize(("prior", "current"), [
    (item(klass="market_research"), item(klass="community_pain")),
    (item(tenant="tenant:a"), item(tenant="tenant:b")),
    (item(tenant=None), item(tenant="tenant:a")),
])
def test_key_reused_for_other_class_or_tenant_is_held(prior, current):
    original = routes(items=[prior])
    original["history"] = build_opportunity_history(original)
    with pytest.raises(ValueError, match="HISTORY_CROSS_TENANT_OR_CLASS_COLLISION"):
        build_opportunity_history(routes(T2, [current]), original)


def test_previous_legacy_router_snapshot_bootstraps_without_pretending_prior_cycles():
    first = routes(items=[item(stage="QUALIFY")])
    out = build_opportunity_history(routes(T2, [item(stage="QUALIFY")]), first)
    assert out["previous_source_status"] == "BOOTSTRAPPED_PREVIOUS_ROUTE"
    assert keyed(out)["first_seen_at"] == T1
    assert keyed(out)["observation_count"] == 2
    assert out["new_identity_count"] == 0


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "LIVE"),
    ("automatic_external_execution_allowed", True),
    ("schema_version", "untrusted.v2"),
])
def test_untrusted_router_snapshot_cannot_seed_history(field, value):
    payload = routes()
    payload[field] = value
    with pytest.raises(ValueError, match="HISTORY_ROUTER_SOURCE_UNTRUSTED"):
        build_opportunity_history(payload)


def test_replay_with_same_or_earlier_cycle_time_is_held():
    old = routes()
    old["history"] = build_opportunity_history(old)
    for when in (T1, "2026-10-11T09:59:00+00:00"):
        with pytest.raises(ValueError, match="HISTORY_CYCLE_MUST_ADVANCE"):
            build_opportunity_history(routes(when), old)


def test_nan_bools_or_naive_clock_cannot_replace_previous():
    for when in ("2026-10-11T10:00:00", "garbage"):
        with pytest.raises(ValueError, match="TIMESTAMP"):
            build_opportunity_history(routes(when))
    payload = routes()
    payload["opportunity_count"] = True
    with pytest.raises(ValueError, match="HISTORY_ROUTE_COUNT_MISMATCH"):
        build_opportunity_history(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("last_observed_stage", "SCALE_TO_REVENUE"),
    ("first_seen_at", "2030-10-11T10:00:00+00:00"),
    ("last_seen_at", "2030-10-11T10:00:00+00:00"),
    ("observation_count", 0),
    ("observation_count", True),
    ("missed_cycles", -1),
    ("missed_cycles", True),
    ("stage_transition_count", 40),
    ("active_in_latest_cycle", False),
    ("execution_authority", "live"),
    ("stage_source", "independently_verified"),
])
def test_forged_previous_lifecycle_cannot_survive_refresh(field, value):
    previous = routes()
    previous["history"] = build_opportunity_history(previous)
    previous["history"]["entries"][0][field] = value
    with pytest.raises(ValueError, match="HISTORY_PREVIOUS_ROW_CONFLICT"):
        build_opportunity_history(routes(T2), previous)


def test_untrusted_duplicate_previous_identity_is_held():
    previous = routes()
    previous["history"] = build_opportunity_history(previous)
    previous["history"]["entries"].append(deepcopy(previous["history"]["entries"][0]))
    with pytest.raises(ValueError, match="HISTORY_PREVIOUS_ROW_CONFLICT"):
        build_opportunity_history(routes(T2), previous)


def test_retention_bound_prevents_silent_history_loss():
    first = routes(items=[
        item(key=f"market:roofing:area{i}") for i in range(500)
    ])
    prior = build_opportunity_history(first)
    assert prior["tracked_identity_count"] == 500
    first["history"] = prior
    with pytest.raises(ValueError, match="HISTORY_RETENTION_LIMIT_HELD"):
        build_opportunity_history(
            routes(T2, [item(key="market:roofing:new")]),
            first,
        )


def _save(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def test_real_router_refresh_preserves_history_without_new_artifact(tmp_path):
    radar = {
        "candidates": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "niche": "roofing", "metro": "denver",
            "trigger": "observed_market_evidence",
            "offer_key": "managed_service",
            "evidence_refs": ["source:a", "source:b"],
        }]
    }
    intake = {
        "items": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "offer_key": "managed_service",
            "evidence_count": 2, "factory_ready": False,
            "blockers": ["buyer_intent_normalized_score_required"],
            "normalization": {"score_evidence": {}},
        }]
    }
    _save(tmp_path, RADAR, radar)
    _save(tmp_path, INTAKE, intake)
    first = refresh_evidence_routes(tmp_path)
    assert first["history"]["new_identity_count"] == 1
    assert first["history"]["stage_counts_current"] == {"QUALIFY": 1}
    assert first["automatic_external_execution_allowed"] is False
    second = refresh_evidence_routes(tmp_path)
    assert second["history"]["new_identity_count"] == 0
    assert second["history"]["entries"][0]["observation_count"] == 2
    assert second["history"]["entries"][0]["last_observed_stage"] == "QUALIFY"
    assert second["history"]["commercial_stage_independently_verified"] is False
    assert set((tmp_path / OUTPUT.parent).glob("*.json")) == {tmp_path / OUTPUT, tmp_path / INTAKE}


def test_corrupt_history_never_overwrites_last_good_routes(tmp_path):
    _save(tmp_path, RADAR, {"candidates": []})
    _save(tmp_path, INTAKE, {"items": []})
    first = refresh_evidence_routes(tmp_path)
    destination = tmp_path / OUTPUT
    assert first["history"]["tracked_identity_count"] == 0
    malformed = deepcopy(first)
    malformed["history"]["execution_authority"] = "LIVE_TRAFFIC"
    destination.write_text(json.dumps(malformed))
    saved = destination.read_bytes()
    with pytest.raises(ValueError, match="HISTORY_PREVIOUS_INVALID"):
        refresh_evidence_routes(tmp_path)
    assert destination.read_bytes() == saved


def test_missing_previous_output_can_bootstrap_from_current_rows_only(tmp_path):
    _save(tmp_path, RADAR, {"candidates": []})
    _save(tmp_path, INTAKE, {"items": []})
    out = refresh_evidence_routes(tmp_path)
    assert out["history"]["previous_source_status"] == "INITIAL"
    assert out["history"]["tracked_identity_count"] == 0
    assert out["history"]["new_identity_count"] == 0
    assert out["execution_authority"] == "none"



def test_duplicate_radar_keys_from_different_tenants_are_held_before_history():
    candidate_a = {
        "opportunity_key": "storm:one",
        "opportunity_class": "storm_commercial_signal",
        "tenant_id": "tenant:a",
        "trigger": "verified_storm",
    }
    candidate_b = {**candidate_a, "tenant_id": "tenant:b"}
    with pytest.raises(ValueError, match="DUPLICATE_RADAR_OPPORTUNITY_KEY_HELD"):
        build_evidence_routes(
            {"candidates": [candidate_a, candidate_b]},
            {"items": [{"opportunity_key": "storm:one"}]},
        )


def test_duplicate_intake_keys_are_held_before_dispatchable_routes():
    candidate = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "niche": "roofing", "metro": "denver",
    }
    intake_row = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "evidence_count": 1,
    }
    with pytest.raises(ValueError, match="AMBIGUOUS_FACTORY_INTAKE_IDENTITY_HELD"):
        build_evidence_routes(
            {"candidates": [candidate]},
            {"items": [intake_row, deepcopy(intake_row)]},
        )


def test_router_preserves_observed_tenant_scope_without_conferring_permissions():
    row = {
        "opportunity_key": "storm:roofing",
        "opportunity_class": "storm_commercial_signal",
        "tenant_id": "tenant:actual",
        "trigger": "storm",
        "niche": "roofing",
    }
    batch = build_evidence_routes(
        {"candidates": [row]},
        {"items": [{
            "opportunity_key": "storm:roofing",
            "opportunity_class": "storm_commercial_signal",
            "evidence_count": 1,
            "blockers": ["independent_evidence_required"],
            "factory_ready": False,
        }]},
    )
    assert batch["items"][0]["tenant_id"] == "tenant:actual"
    assert batch["items"][0]["execution_authority"] == "none"
    history = build_opportunity_history(batch)
    assert keyed(history, "storm:roofing")["tenant_id"] == "tenant:actual"
    assert history["automatic_external_execution_allowed"] is False


def test_radar_source_identity_is_not_reinterpreted_as_buyer_evidence():
    candidate = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "niche": "roofing", "metro": "denver",
        "trigger": "research",
        "evidence_refs": ["public:one"],
    }
    batch = build_evidence_routes(
        {"candidates": [candidate]},
        {"items": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "evidence_count": 1,
            "factory_ready": False,
            "blockers": ["buyer_intent_normalized_score_required"],
        }]},
    )
    history = build_opportunity_history(batch)
    assert history["stage_counts_current"] == {"DISCOVER": 1}
    assert history["commercial_stage_independently_verified"] is False
    assert batch["items"][0]["execution_authority"] == "none"


@pytest.mark.parametrize("key", [
    "someone@example.com",
    "<script>alert(1)</script>",
    "market:roofing:denver\nnext",
    "market:roofing:denver?token=secret",
    "market:" + "x"*300,
])
def test_history_rejects_noncanonical_keys_and_pii(key):
    with pytest.raises(ValueError, match="HISTORY_IDENTITY_NOT_CANONICAL"):
        build_opportunity_history(routes(items=[item(key=key)]))


def test_malformed_legacy_previous_route_prevents_silent_bootstrap():
    old = routes()
    old["items"][0]["lifecycle"]["current_stage"] = "FAKE_VERIFIED"
    with pytest.raises(ValueError, match="HISTORY_LEGACY_DUPLICATE_OR_INVALID_STAGE"):
        build_opportunity_history(routes(T2), old)


def test_history_same_subject_with_new_class_cannot_inherit_old_stage():
    old = routes(items=[item(klass="market_research", stage="PROVE")])
    old["history"] = build_opportunity_history(old)
    current = routes(T2, [item(klass="community_pain", stage="DISCOVER")])
    with pytest.raises(ValueError, match="HISTORY_CROSS_TENANT_OR_CLASS_COLLISION"):
        build_opportunity_history(current, old)


def test_unreadable_previous_router_blocks_refresh_and_preserves_bytes(tmp_path):
    _save(tmp_path, RADAR, {"candidates": []})
    _save(tmp_path, INTAKE, {"items": []})
    path = tmp_path / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"{garbled-json")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="OPPORTUNITY_HISTORY_PREVIOUS_OUTPUT_UNREADABLE"):
        refresh_evidence_routes(tmp_path)
    assert path.read_bytes() == before
