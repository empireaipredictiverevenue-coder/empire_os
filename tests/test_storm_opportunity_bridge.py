from datetime import datetime, timedelta, timezone

from empire_os.storm_opportunity_bridge import storm_assessment_to_opportunity
from empire_os.storm_product_integration import (
    AffectedSubject,
    BuyerProductMatch,
    Evidence,
    StormEvent,
    SubjectKind,
    TruthClass,
    assess_storm_product,
)


def _fixture():
    now = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)

    def evidence(ref):
        return Evidence(
            tenant_id="tenant-1",
            ref=ref,
            source="test",
            observed_at=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
        )

    event = StormEvent(
        tenant_id="tenant-1",
        event_id="storm-1",
        event_type="hail",
        severity="severe",
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(hours=1),
        truth_class=TruthClass.OBSERVED,
        evidence=(evidence("event:1"),),
    )
    subject = AffectedSubject(
        tenant_id="tenant-1",
        event_id="storm-1",
        canonical_id="property-1",
        kind=SubjectKind.PROPERTY,
        niche="roofing",
        territory_id="denver",
        confidence=0.9,
        territory_overlap=0.8,
        evidence=(evidence("subject:1"),),
    )
    match = BuyerProductMatch(
        tenant_id="tenant-1",
        buyer_id="buyer-1",
        product_id="product-1",
        niche="roofing",
        territory_id="denver",
        evidence=(evidence("match:1"),),
    )
    assessment = assess_storm_product(
        event,
        subject,
        match,
        now=now,
    )
    return event, subject, assessment


def test_bridge_preserves_truth_and_authority_boundaries():
    event, subject, assessment = _fixture()
    row = storm_assessment_to_opportunity(event, subject, assessment)

    assert row["tenant_id"] == "tenant-1"
    assert row["event_id"] == "storm-1"
    assert row["subject_id"] == "property-1"
    assert row["buyer_id"] == "buyer-1"
    assert row["product_id"] == "product-1"

    assert row["source"] == "storm_product_integration"
    assert row["trigger"] == "observed_storm_commercial_signal"

    assert set(row["evidence_refs"]) >= {
        "event:1",
        "subject:1",
        "match:1",
    }

    assert row["buyer_intent_inferred"] is False
    assert row["demand_inferred"] is False
    assert row["revenue_inferred"] is False
    assert row["economics"] is None
    assert row["opportunity_factory_ready"] is False
    assert row["commercial_ready"] is False

    assert "founder_commercial_authority_required" in row["storm_blockers"]

    assert row["execution_authority"] == "none"
    assert row["outreach_authority"] == "none"
    assert row["traffic_authority"] == "none"
    assert row["commercial_authority"] == "none"
    assert row["payment_authority"] == "none"


def test_bridge_identity_is_deterministic():
    event, subject, assessment = _fixture()

    first = storm_assessment_to_opportunity(event, subject, assessment)
    second = storm_assessment_to_opportunity(event, subject, assessment)

    assert first["opportunity_key"] == second["opportunity_key"]


def test_storm_multiplier_does_not_become_factory_scores():
    event, subject, assessment = _fixture()
    row = storm_assessment_to_opportunity(event, subject, assessment)

    assert "buyer_intent" not in row
    assert "demand" not in row
    assert "urgency" not in row
    assert "margin_potential" not in row
    assert "distribution_strength" not in row
    assert "data_advantage" not in row
    assert "fulfilment_readiness" not in row
    assert "build_complexity" not in row

    if row["storm_model"] is not None:
        assert row["storm_model"]["multiplier"] == assessment.score.multiplier


def test_snapshot_is_json_safe_and_preserves_fail_closed_authority():
    import json

    from empire_os.storm_opportunity_bridge import (
        build_storm_opportunity_snapshot,
    )

    event, subject, assessment = _fixture()
    row = storm_assessment_to_opportunity(event, subject, assessment)

    snapshot = build_storm_opportunity_snapshot(
        [row],
        generated_at="2026-10-05T09:00:00+00:00",
    )

    encoded = json.dumps(snapshot, sort_keys=True)

    assert encoded
    assert snapshot["mode"] == "OBSERVE"
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["tenant_id"] == "tenant-1"

    assert snapshot["automatic_external_execution_allowed"] is False
    assert snapshot["execution_authority"] == "none"
    assert snapshot["outreach_authority"] == "none"
    assert snapshot["traffic_authority"] == "none"
    assert snapshot["commercial_authority"] == "none"
    assert snapshot["payment_authority"] == "none"
    assert snapshot["revenue_recognition_authority"] == "none"


def test_snapshot_rejects_duplicate_opportunity_identity():
    from empire_os.storm_opportunity_bridge import (
        build_storm_opportunity_snapshot,
    )

    event, subject, assessment = _fixture()
    row = storm_assessment_to_opportunity(event, subject, assessment)

    snapshot = build_storm_opportunity_snapshot(
        [row, dict(row)],
        generated_at="2026-10-05T09:00:00+00:00",
    )

    assert snapshot["candidate_count"] == 1


def test_snapshot_does_not_restore_commercial_authority():
    from empire_os.storm_opportunity_bridge import (
        build_storm_opportunity_snapshot,
    )

    event, subject, assessment = _fixture()
    row = storm_assessment_to_opportunity(event, subject, assessment)

    hostile = dict(row)
    hostile["execution_authority"] = "execute"
    hostile["outreach_authority"] = "send"
    hostile["traffic_authority"] = "activate"
    hostile["commercial_authority"] = "bind"
    hostile["payment_authority"] = "move_funds"
    hostile["commercial_ready"] = True
    hostile["revenue_inferred"] = True

    snapshot = build_storm_opportunity_snapshot(
        [hostile],
        generated_at="2026-10-05T09:00:00+00:00",
    )
    candidate = snapshot["candidates"][0]

    assert candidate["execution_authority"] == "none"
    assert candidate["outreach_authority"] == "none"
    assert candidate["traffic_authority"] == "none"
    assert candidate["commercial_authority"] == "none"
    assert candidate["payment_authority"] == "none"
    assert candidate["commercial_ready"] is False
    assert candidate["revenue_inferred"] is False
