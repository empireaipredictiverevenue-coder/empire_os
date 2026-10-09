from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.storm_intelligence_runtime import (
    build_storm_intelligence_runtime,
    materialize_storm_intelligence,
)


NOW = datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)


def evidence(ref: str, *, tenant="tenant-1", source="nws"):
    return {
        "tenant_id": tenant,
        "ref": ref,
        "source": source,
        "observed_at": (NOW - timedelta(minutes=30)).isoformat(),
        "valid_until": (NOW + timedelta(hours=6)).isoformat(),
    }


def event(**overrides):
    row = {
        "tenant_id": "tenant-1",
        "event_id": "storm-1",
        "event_type": "hail",
        "severity": "severe",
        "starts_at": (NOW - timedelta(hours=2)).isoformat(),
        "ends_at": (NOW - timedelta(hours=1)).isoformat(),
        "truth_class": "OBSERVED",
        "evidence": [evidence("event:nws:storm-1")],
    }
    row.update(overrides)
    return row


def subject(**overrides):
    row = {
        "tenant_id": "tenant-1",
        "event_id": "storm-1",
        "canonical_id": "property-1",
        "kind": "property",
        "niche": "roofing",
        "territory_id": "territory-dfw",
        "confidence": 0.90,
        "territory_overlap": 0.85,
        "evidence": [
            evidence(
                "empiredb:property:property-1:storm-1",
                source="empiredb",
            )
        ],
    }
    row.update(overrides)
    return row


def match(**overrides):
    row = {
        "tenant_id": "tenant-1",
        "buyer_id": "buyer-1",
        "product_id": "roofing-lead",
        "niche": "roofing",
        "territory_id": "territory-dfw",
        "evidence": [
            evidence(
                "empiredb:buyer-product:buyer-1:roofing-lead",
                source="empiredb",
            )
        ],
    }
    row.update(overrides)
    return row


def build(**overrides):
    kwargs = {
        "events": [event()],
        "subjects": [subject()],
        "matches": [match()],
        "now": NOW,
    }
    kwargs.update(overrides)
    return build_storm_intelligence_runtime(**kwargs)


def test_valid_evidenced_path_emits_one_observe_opportunity():
    snapshot = build()

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]

    assert candidate["tenant_id"] == "tenant-1"
    assert candidate["event_id"] == "storm-1"
    assert candidate["subject_id"] == "property-1"
    assert candidate["buyer_id"] == "buyer-1"
    assert candidate["product_id"] == "roofing-lead"

    assert candidate["exposure"]["state"] == "INFERRED"
    assert candidate["exposure"]["damage_verified"] is False

    assert candidate["economic_opportunity"]["state"] == "UNKNOWN"
    assert candidate["economic_opportunity"]["expected_revenue_value_cents"] is None

    assert candidate["commercial_ready"] is False
    assert candidate["revenue_inferred"] is False

    for key in (
        "execution_authority",
        "outreach_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
    ):
        assert candidate[key] == "none"


def test_identity_is_deterministic():
    first = build()["candidates"][0]["opportunity_key"]
    second = build()["candidates"][0]["opportunity_key"]
    assert first == second


def test_event_without_evidence_fails_closed():
    snapshot = build(events=[event(evidence=[])])

    assert snapshot["candidate_count"] == 0
    assert snapshot["diagnostics"]["events_valid"] == 0
    assert snapshot["diagnostics"]["events_rejected"] == 1


def test_subject_tenant_mismatch_fails_closed():
    snapshot = build(subjects=[subject(tenant_id="tenant-2")])

    assert snapshot["candidate_count"] == 0
    assert snapshot["diagnostics"]["subjects_supported"] == 0


def test_subject_event_mismatch_fails_closed():
    snapshot = build(subjects=[subject(event_id="other-storm")])

    assert snapshot["candidate_count"] == 0
    assert snapshot["diagnostics"]["subjects_supported"] == 0


def test_missing_subject_does_not_fabricate_damage_or_opportunity():
    snapshot = build(subjects=[])

    assert snapshot["candidate_count"] == 0
    assert snapshot["damage_inferred"] is False
    assert snapshot["diagnostics"]["blocked_count"] >= 1
    assert any(
        item["required"] == "canonical_subject_evidence_required"
        for item in snapshot["diagnostics"]["next_best_evidence"]
    )


def test_missing_buyer_product_match_does_not_fabricate_demand():
    snapshot = build(matches=[])

    assert snapshot["candidate_count"] == 0
    assert snapshot["buyer_intent_inferred"] is False
    assert snapshot["demand_inferred"] is False
    assert any(
        item["required"] == "buyer_product_evidence_required"
        for item in snapshot["diagnostics"]["next_best_evidence"]
    )


def test_niche_mismatch_does_not_create_match():
    snapshot = build(matches=[match(niche="solar")])
    assert snapshot["candidate_count"] == 0


def test_territory_mismatch_does_not_create_match():
    snapshot = build(matches=[match(territory_id="territory-other")])
    assert snapshot["candidate_count"] == 0


def test_forecast_event_never_becomes_observed_fact():
    snapshot = build(events=[event(truth_class="FORECAST")])

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]

    assert candidate["event_truth_class"] == "FORECAST"
    assert candidate["storm_model"] is None
    assert "observed_event_required" in candidate["storm_blockers"]
    assert candidate["commercial_ready"] is False


def test_stale_event_evidence_blocks_model_promotion():
    stale = evidence("event:nws:storm-1")
    stale["observed_at"] = (NOW - timedelta(days=2)).isoformat()
    stale["valid_until"] = (NOW - timedelta(days=1)).isoformat()

    snapshot = build(events=[event(evidence=[stale])])

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]

    assert candidate["storm_model"] is None
    assert "event_or_subject_evidence_stale_or_future" in candidate["storm_blockers"]


def test_future_event_evidence_blocks_model_promotion():
    future = evidence("event:nws:storm-1")
    future["observed_at"] = (NOW + timedelta(minutes=5)).isoformat()
    future["valid_until"] = (NOW + timedelta(hours=2)).isoformat()

    snapshot = build(events=[event(evidence=[future])])

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]

    assert candidate["storm_model"] is None
    assert "event_or_subject_evidence_stale_or_future" in candidate["storm_blockers"]


def test_duplicate_identical_event_is_bounded():
    row = event()
    snapshot = build(events=[row, dict(row)])

    assert snapshot["diagnostics"]["events_deduplicated"] == 1
    assert snapshot["diagnostics"]["events_valid"] == 1
    assert snapshot["candidate_count"] == 1


def test_conflicting_duplicate_event_fails_closed():
    first = event()
    second = event(severity="extreme")

    snapshot = build(events=[first, second])

    assert snapshot["candidate_count"] == 0
    assert snapshot["diagnostics"]["evidence_conflict_count"] == 1
    assert snapshot["diagnostics"]["events_valid"] == 0


def test_empty_runtime_is_valid_observe_snapshot():
    snapshot = build_storm_intelligence_runtime(now=NOW)

    assert snapshot["mode"] == "OBSERVE"
    assert snapshot["candidate_count"] == 0
    assert snapshot["diagnostics"]["source_health"] == "NO_DATA"
    assert snapshot["automatic_external_execution_allowed"] is False
    assert snapshot["execution_authority"] == "none"


def test_malformed_item_isolated_while_valid_event_continues():
    snapshot = build(events=[{"bad": "row"}, event()])

    assert snapshot["diagnostics"]["events_seen"] == 2
    assert snapshot["diagnostics"]["events_rejected"] == 1
    assert snapshot["diagnostics"]["events_valid"] == 1
    assert snapshot["candidate_count"] == 1


def test_atomic_materializer_writes_valid_snapshot(tmp_path):
    snapshot = materialize_storm_intelligence(
        tmp_path,
        events=[event()],
        subjects=[subject()],
        matches=[match()],
        now=NOW,
    )

    path = tmp_path / "runtime/storm_opportunity/latest.json"
    assert path.exists()

    persisted = json.loads(path.read_text())
    assert persisted == snapshot
    assert persisted["candidate_count"] == 1

    leftovers = list(path.parent.glob(".latest.json.*.tmp"))
    assert leftovers == []


def test_rerun_is_idempotent_at_identity_level(tmp_path):
    first = materialize_storm_intelligence(
        tmp_path,
        events=[event()],
        subjects=[subject()],
        matches=[match()],
        now=NOW,
    )
    second = materialize_storm_intelligence(
        tmp_path,
        events=[event()],
        subjects=[subject()],
        matches=[match()],
        now=NOW,
    )

    assert first["candidate_count"] == second["candidate_count"] == 1
    assert (
        first["candidates"][0]["opportunity_key"]
        == second["candidates"][0]["opportunity_key"]
    )


def test_readiness_missing_remains_explicit_blocker():
    snapshot = build()
    blockers = snapshot["candidates"][0]["storm_blockers"]

    assert "capacity_evidence_required" in blockers
    assert "buyer_approval_evidence_required" in blockers
    assert "approved_terms_evidence_required" in blockers
    assert "founder_commercial_authority_required" in blockers


def test_no_runtime_path_can_claim_revenue_or_external_authority():
    snapshot = build()
    candidate = snapshot["candidates"][0]

    assert snapshot["revenue_recognition_authority"] == "none"
    assert snapshot["automatic_external_execution_allowed"] is False
    assert snapshot["economics_inferred"] is False

    assert candidate["economics"] is None
    assert candidate["revenue_inferred"] is False
    assert candidate["commercial_ready"] is False
    assert candidate["opportunity_factory_ready"] is False
