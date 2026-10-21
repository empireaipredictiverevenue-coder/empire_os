"""Reproducible point-in-time feature manifests: no forecast or DB claims."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.predictive_point_in_time_features import (
    TemporalEvidenceHold, review_point_in_time_features,
)

TENANT = "4ec7c503-b78f-4201-ad2a-2a00f7b1b6f4"
H = "a" * 64
DECISION = "2026-10-20T12:00:00+00:00"
NOW = "2026-10-21T12:00:00+00:00"


def source(source_ref="buyer_cap", revision=1, *,
           observed="2026-10-19T09:00:00+00:00",
           available="2026-10-19T10:00:00+00:00",
           ingested="2026-10-19T11:00:00+00:00",
           tenant=TENANT, kind="buyer_capacity"):
    return {
        "tenant_id": tenant, "source_kind": kind,
        "source_ref": source_ref, "revision": revision,
        "observed_at": observed, "first_available_at": available,
        "ingested_at": ingested, "evidence_sha256": H,
    }


def review(rows, **kwargs):
    return review_point_in_time_features(
        rows, tenant_id=TENANT, decision_at=DECISION, review_at=NOW, **kwargs
    )


def test_asof_digest_deterministic_order_independent_and_denies_customer_claims():
    first = source()
    other = source(source_ref="original_terms", kind="commercial_terms")
    original = review([first, other])
    shuffled = review([other, first])
    assert original == shuffled
    assert original["distinct_sources_available_as_of"] == 2
    assert original["source_kind_counts_as_of"]["buyer_capacity"] == 1
    assert original["source_kind_counts_as_of"]["commercial_terms"] == 1
    assert original["as_of_replay_deterministic"] is True
    for field in (
        "source_issuer_authenticated_by_input", "independent_source_custody_verified",
        "original_forecast_issued", "real_customer_outcome_verified",
        "eligible_for_scientific_training", "customer_prediction_authorized",
        "raw_customer_records_exposed", "database_writes",
    ):
        assert original[field] is False
    text = json.dumps(original)
    assert TENANT not in text and "original_terms" not in text


def test_late_backfill_cannot_change_historical_manifest():
    original = review([source()])
    backfill = source(
        source_ref="buyer_cap", revision=2,
        observed="2026-10-19T09:00:00+00:00",
        available="2026-10-20T13:00:00+00:00",
        ingested="2026-10-20T14:00:00+00:00",
    )
    later = review([source(), backfill])
    assert later["feature_manifest_sha256"] == original["feature_manifest_sha256"]
    assert later["source_revisions_withheld_after_decision"] == 1
    assert later["future_event_records_excluded"] == 0


def test_ingestion_after_decision_excluded_despite_earlier_first_availability():
    delayed = source(
        source_ref="slow",
        observed="2026-10-19T09:00:00+00:00",
        available="2026-10-19T10:00:00+00:00",
        ingested="2026-10-20T12:00:01+00:00",
    )
    result = review([source(), delayed])
    assert result["distinct_sources_available_as_of"] == 1
    assert result["source_revisions_withheld_after_decision"] == 1


def test_future_event_excluded_without_lookahead():
    item = source(
        source_ref="tomorrow",
        observed="2026-10-20T12:30:00+00:00",
        available="2026-10-20T12:40:00+00:00",
        ingested="2026-10-20T13:00:00+00:00",
    )
    result = review([source(), item])
    assert result["future_event_records_excluded"] == 1
    assert result["distinct_sources_available_as_of"] == 1


def test_revision_selection_uses_latest_predecision_revision_only():
    old = source(revision=1)
    revised = source(revision=2, observed="2026-10-19T10:00:00+00:00",
                     available="2026-10-19T12:00:00+00:00",
                     ingested="2026-10-19T13:00:00+00:00")
    only_revised = review([revised])
    combined = review([old, revised])
    assert combined["feature_manifest_sha256"] == only_revised["feature_manifest_sha256"]
    assert combined["distinct_sources_available_as_of"] == 1


@pytest.mark.parametrize("bad", [
    [source(tenant="00000000-0000-4000-8000-000000000099")],
    [source(), source()],
    [source(available="2026-10-18T08:00:00+00:00")],
    [source(ingested="2026-10-18T08:00:00+00:00")],
    [source(observed="2026-10-23T08:00:00+00:00", available="2026-10-23T09:00:00+00:00", ingested="2026-10-23T10:00:00+00:00")],
    [source(revision=True)],
    [source(kind="unapproved_customer_value")],
    [dict(source(), evidence_sha256="NOT_A_DIGEST")],
    [dict(source(), tenant_id=None)],
    [dict(source(), arbitrary_extra_field="x")],
    [dict(source(), first_available_at="2026-10-19T10:00:00")],
    [dict(source(), ingested_at="2026-10-19T11:00:00Z" * 30)],
])
def test_invalid_sources_hold_all_evidence(bad):
    with pytest.raises(TemporalEvidenceHold):
        review(bad)


def test_empty_cohort_never_becomes_verified_zero_revenue():
    result = review([])
    assert result["distinct_sources_available_as_of"] == 0
    assert result["customer_prediction_authorized"] is False
    assert result["real_customer_outcome_verified"] is False


def test_bounded_and_invalid_tenant_refused():
    with pytest.raises(TemporalEvidenceHold):
        review([source()] * 501)
    with pytest.raises(TemporalEvidenceHold):
        review_point_in_time_features([], tenant_id="not-a-tenant", decision_at=DECISION, review_at=NOW)
