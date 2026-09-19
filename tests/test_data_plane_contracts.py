import hashlib

import pytest

from empire_os.data_plane_contracts import (
    build_event_envelope,
    build_lineage_run,
    build_point_in_time_feature,
    build_raw_evidence_ref,
    canonical_payload_hash,
)


def sha(text="hello"):
    return hashlib.sha256(text.encode()).hexdigest()


def test_raw_evidence_pointer_is_immutable_preview():
    result = build_raw_evidence_ref({
        "evidence_ref": "raw.permit.123",
        "source_key": "permit.miami",
        "content_sha256": sha(),
        "media_type": "application/json",
        "byte_size": 42,
        "collected_at": "2026-09-20T00:00:00+00:00",
        "privacy_class": "PUBLIC",
        "immutable": True,
    })
    assert result["immutable"] is True
    assert result["storage_mutation"] is False
    assert result["execution_authority"] == "none"


def test_raw_evidence_rejects_mutable_or_bad_hash():
    with pytest.raises(ValueError):
        build_raw_evidence_ref({
            "evidence_ref": "raw.permit.123",
            "source_key": "permit.miami",
            "content_sha256": "bad",
            "media_type": "application/json",
            "byte_size": 42,
            "collected_at": "2026-09-20T00:00:00+00:00",
            "privacy_class": "PUBLIC",
            "immutable": True,
        })
    with pytest.raises(ValueError, match="immutable"):
        build_raw_evidence_ref({
            "evidence_ref": "raw.permit.123",
            "source_key": "permit.miami",
            "content_sha256": sha(),
            "media_type": "application/json",
            "byte_size": 42,
            "collected_at": "2026-09-20T00:00:00+00:00",
            "privacy_class": "PUBLIC",
            "immutable": False,
        })


def test_event_envelope_hash_is_deterministic_and_unpersisted():
    payload = {"permit_id": "P-1", "value": 1000}
    first = build_event_envelope({
        "event_id": "evt-1",
        "event_type": "permit.observed",
        "aggregate_type": "permit",
        "aggregate_id": "P-1",
        "schema_version": "v1",
        "source_key": "permit.miami",
        "observed_at": "2026-09-20T00:00:00+00:00",
        "emitted_at": "2026-09-20T00:00:05+00:00",
        "correlation_id": "corr-1",
        "idempotency_key": "permit:P-1:20260920",
        "evidence_refs": ["raw.permit.123"],
        "payload": payload,
    })
    second_hash = canonical_payload_hash({"value": 1000, "permit_id": "P-1"})
    assert first["payload_hash"] == second_hash
    assert first["persisted"] is False
    assert first["execution_authority"] == "none"


def test_event_envelope_requires_chronology_and_evidence():
    with pytest.raises(ValueError, match="precede"):
        build_event_envelope({
            "event_id": "evt-1",
            "event_type": "x",
            "aggregate_type": "x",
            "aggregate_id": "1",
            "schema_version": "v1",
            "source_key": "source.x",
            "observed_at": "2026-09-20T00:00:05+00:00",
            "emitted_at": "2026-09-20T00:00:00+00:00",
            "correlation_id": "corr",
            "idempotency_key": "idem",
            "evidence_refs": ["raw.x.1"],
            "payload": {},
        })


def test_lineage_run_preserves_counts_cost_and_refs():
    result = build_lineage_run({
        "run_id": "run-1",
        "transformation_key": "permit.normalize",
        "transformation_version": "v1",
        "code_commit": "abc123",
        "started_at": "2026-09-20T00:00:00+00:00",
        "completed_at": "2026-09-20T00:00:10+00:00",
        "input_refs": ["raw.permit.123"],
        "output_refs": ["fact.permit.123"],
        "input_count": 10,
        "output_count": 8,
        "rejected_count": 1,
        "quarantined_count": 1,
        "cost_cents": 25,
    })
    assert result["accepted_input_count"] == 8
    assert result["cost_cents"] == 25
    assert result["persisted"] is False


def test_point_in_time_feature_blocks_leakage_chronology():
    result = build_point_in_time_feature({
        "feature_key": "corridor.permit_activity_30d",
        "entity_type": "corridor",
        "entity_id": "roofing:manchester",
        "feature_version": "v1",
        "transformation_version": "v2",
        "feature_time": "2026-09-19T00:00:00+00:00",
        "materialized_at": "2026-09-19T00:05:00+00:00",
        "value": 12,
        "source_refs": ["fact.permit.1"],
        "outcome_time": "2026-09-20T00:00:00+00:00",
    })
    assert result["point_in_time_correct"] is True
    assert result["future_outcome_leakage"] is False

    with pytest.raises(ValueError, match="after feature_time"):
        build_point_in_time_feature({
            "feature_key": "corridor.permit_activity_30d",
            "entity_type": "corridor",
            "entity_id": "roofing:manchester",
            "feature_version": "v1",
            "transformation_version": "v2",
            "feature_time": "2026-09-20T00:00:00+00:00",
            "materialized_at": "2026-09-20T00:05:00+00:00",
            "value": 12,
            "source_refs": ["fact.permit.1"],
            "outcome_time": "2026-09-19T00:00:00+00:00",
        })
