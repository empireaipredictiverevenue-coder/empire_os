import copy

import pytest

from empire_os.opportunity_source_convergence import (
    build_source_convergence_snapshot,
    revenue_pulse_leak_candidates,
)


def _pulse():
    return {
        "schema_version": "empire.revenue-pulse.v3",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "execution_allowed": False,
        "payment_mutation": False,
        "revenue_mutation": False,
        "accounting_mutation": False,
        "leak_detection": {
            "method": "observed_zero_conversion_only",
            "prediction": False,
            "items": [
                {
                    "from_stage": "delivered_outreach",
                    "to_stage": "commercial_replies",
                    "entered": 81,
                    "converted": 0,
                    "conversion_rate": 0.0,
                    "state": "observed_zero_conversion",
                    "prediction": False,
                }
            ],
        },
        "recognized_revenue_truth": {
            "recognized_revenue_cents": 0,
            "realized_gp_cents": 0,
            "forecast_included_in_truth": False,
        },
        "evidence_refs": [
            "commercial_events:delivered",
            "closer_events:commercial_reply",
        ],
    }


def test_observed_leak_becomes_truth_preserving_candidate():
    rows = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )

    assert len(rows) == 1
    row = rows[0]

    assert row["source"] == "revenue_pulse"
    assert row["source_kind"] == "revenue_leak"
    assert row["tenant_id"] == "tenant-1"
    assert row["opportunity_key"].startswith("revenue_leak_")

    assert row["observed_condition"]["entered"] == 81
    assert row["observed_condition"]["converted"] == 0

    assert row["prediction"] is False
    assert row["predicted_revenue_cents"] is None
    assert row["recognized_revenue_cents"] is None
    assert row["estimated_recovery_value_cents"] is None
    assert row["confidence"] is None

    assert row["opportunity_factory_ready"] is False
    assert row["requires_evidence_completion"] is True


def test_candidate_never_inherits_execution_authority():
    row = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )[0]

    for field in (
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert row[field] == "none"

    assert row["automatic_external_execution_allowed"] is False
    assert row["commercial_ready"] is False
    assert row["revenue_inferred"] is False


def test_wrong_schema_fails_closed():
    payload = _pulse()
    payload["schema_version"] = "legacy"

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_non_observe_source_fails_closed():
    payload = _pulse()
    payload["mode"] = "EXECUTE"

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_upstream_execution_authority_fails_closed():
    payload = _pulse()
    payload["execution_authority"] = "granted"

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_execution_allowed_true_fails_closed():
    payload = _pulse()
    payload["execution_allowed"] = True

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_prediction_based_leak_fails_closed():
    payload = _pulse()
    payload["leak_detection"]["prediction"] = True

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_missing_evidence_fails_closed():
    payload = _pulse()
    payload["evidence_refs"] = []

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_nonzero_conversion_is_not_zero_conversion_leak():
    payload = _pulse()
    payload["leak_detection"]["items"][0]["converted"] = 4

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_candidate_key_is_deterministic():
    first = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )[0]

    second = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )[0]

    assert first["opportunity_key"] == second["opportunity_key"]


def test_tenant_changes_identity():
    first = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )[0]

    second = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-2",
    )[0]

    assert first["opportunity_key"] != second["opportunity_key"]


def test_source_evidence_changes_identity():
    first = revenue_pulse_leak_candidates(
        _pulse(),
        tenant_id="tenant-1",
    )[0]

    changed = _pulse()
    changed["evidence_refs"].append("window:2026-10-06")

    second = revenue_pulse_leak_candidates(
        changed,
        tenant_id="tenant-1",
    )[0]

    assert first["opportunity_key"] != second["opportunity_key"]


def test_tampered_item_claiming_prediction_is_rejected():
    payload = _pulse()
    payload["leak_detection"]["items"][0]["prediction"] = True

    assert revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    ) == []


def test_snapshot_preserves_observe_authority():
    snapshot = build_source_convergence_snapshot(
        tenant_id="tenant-1",
        revenue_pulse=_pulse(),
    )

    assert snapshot["mode"] == "OBSERVE"
    assert snapshot["candidate_count"] == 1
    assert snapshot["source_counts"]["revenue_leak"] == 1

    assert snapshot["execution_authority"] == "none"
    assert snapshot["commercial_authority"] == "none"
    assert snapshot["payment_authority"] == "none"
    assert snapshot["automatic_external_execution_allowed"] is False


def test_missing_source_is_valid_empty_snapshot():
    snapshot = build_source_convergence_snapshot(
        tenant_id="tenant-1",
        revenue_pulse=None,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["source_counts"]["revenue_leak"] == 0


def test_tenant_required():
    with pytest.raises(ValueError, match="tenant_id required"):
        build_source_convergence_snapshot(
            tenant_id="",
            revenue_pulse=_pulse(),
        )


def test_input_is_not_mutated():
    payload = _pulse()
    before = copy.deepcopy(payload)

    revenue_pulse_leak_candidates(
        payload,
        tenant_id="tenant-1",
    )

    assert payload == before
