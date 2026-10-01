from datetime import datetime, timezone

import pytest

from empire_os.commercial_opportunity_decay import (
    assess_opportunity_decay,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def test_recent_revalidation_keeps_old_opportunity_active():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:1",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "revalidated_at": "2026-10-01T11:30:00+00:00",
        "freshness_window_seconds": 86400,
        "buyer_need_until": "2026-10-10T00:00:00+00:00",
        "evidence_refs": ["permit:1", "revalidation:1"],
    }, as_of=NOW)

    assert result.state == "ACTIVE"
    assert result.recency_factor_candidate is None
    assert result.actual_revenue is False


def test_explicit_hard_expiry_has_precedence():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:2",
        "revalidated_at": "2026-10-01T11:30:00+00:00",
        "freshness_window_seconds": 86400,
        "source_expires_at": "2026-09-30T23:59:00+00:00",
        "evidence_refs": ["buyer-need:expired"],
    }, as_of=NOW)

    assert result.state == "EXPIRED"
    assert result.expired_fields == ("source_expires_at",)
    assert result.recency_factor_candidate is None


def test_stale_freshness_does_not_invent_numeric_decay():
    result = assess_opportunity_decay({
        "opportunity_key": "market:3",
        "revalidated_at": "2026-09-29T12:00:00+00:00",
        "freshness_window_seconds": 86400,
        "evidence_refs": ["market-snapshot:3"],
    }, as_of=NOW)

    assert result.state == "STALE"
    assert result.stale_by_seconds == 86400
    assert result.recency_factor_candidate is None


def test_created_age_without_temporal_contract_is_unknown():
    result = assess_opportunity_decay({
        "opportunity_key": "legacy:4",
        "observed_at": "2025-01-01T00:00:00+00:00",
        "evidence_refs": ["legacy:4"],
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert "temporal_validity_contract_missing" in result.blockers


def test_missing_evidence_refs_fails_closed():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:5",
        "revalidated_at": "2026-10-01T11:00:00+00:00",
        "freshness_window_seconds": 86400,
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert result.recency_factor_candidate is None
    assert "evidence_refs_missing" in result.blockers


def test_missing_validation_for_freshness_policy_is_unknown():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:6",
        "freshness_window_seconds": 86400,
        "evidence_refs": ["source-policy:permit"],
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert "validation_timestamp_missing" in result.blockers


def test_naive_timestamp_is_rejected():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:7",
        "observed_at": "2026-10-01T10:00:00",
        "freshness_window_seconds": 86400,
        "evidence_refs": ["permit:7"],
    }, as_of=NOW)
    assert result.state == "UNKNOWN"
    assert "timezone-aware" in result.blockers[0]


def test_candidate_never_grants_execution_authority():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:8",
        "source_expires_at": "2026-10-05T00:00:00+00:00",
        "evidence_refs": ["source:8"],
    }, as_of=NOW)

    assert result.state == "ACTIVE"
    assert result.recommendation_only is True
    assert result.allocation_authorized is False
    assert result.outreach_authorized is False
    assert result.payment_authorized is False
    assert result.execution_authority == "none"


def component(**changes):
    return {
        "observed_at": "2026-10-01T11:00:00Z",
        "freshness_window_seconds": 7200,
        "evidence_refs": ["component:1"],
        **changes,
    }


def commercial(**changes):
    return component(
        retained_value_ratio=0.73,
        effective_from="2026-10-01T12:00:00Z",
        effective_until="2026-10-02T12:00:00Z",
        basis="validated_calibration", basis_ref="calibration:1", **changes,
    )


def assess(**changes):
    return assess_opportunity_decay({
        "opportunity_key": "permit:1",
        "source_expires_at": "2026-10-02T12:00:00Z",
        "evidence_refs": ["source:1"], **changes,
    }, as_of=NOW)


def test_commercial_ratio_preserved_without_transport_or_other_effects():
    result = assess(commercial_value=commercial()).as_dict()
    assert result["commercial_value"]["retained_value_ratio"] == 0.73
    assert result["recency_factor_candidate"] == 0.73
    assert result["erv_transport_authorized"] is False
    assert result["revenue_recognition_authority"] == "none"
    assert "predictive_revenue_inputs" not in result


@pytest.mark.parametrize("field,value", [
    ("basis", None), ("basis_ref", ""), ("evidence_refs", []),
    ("evidence_refs", [None]), ("retained_value_ratio", True),
    ("retained_value_ratio", float("nan")), ("retained_value_ratio", float("inf")),
    ("retained_value_ratio", -0.1), ("retained_value_ratio", 1.1),
    ("effective_until", "2026-10-01T12:00:00Z"),
    ("effective_from", "2026-10-01T12:00:01Z"),
    ("effective_from", "2026-10-01T12:00:00"),
    ("observed_at", "2026-10-01T12:00:01Z"),
    ("freshness_window_seconds", True), ("freshness_window_seconds", 1.5),
    ("freshness_window_seconds", 3600),
    ("opportunity_key", "different"),
])
def test_invalid_commercial_evidence_is_unknown(field, value):
    data = commercial()
    data[field] = value
    result = assess(commercial_value=data)
    assert result.state == "ACTIVE"
    assert result.commercial_value["state"] == "UNKNOWN"
    assert result.recency_factor_candidate is None


@pytest.mark.parametrize("ratio", [0, 1, 0.123456789])
def test_ratio_endpoints_are_evidence_not_temporal_defaults(ratio):
    data = commercial()
    data["retained_value_ratio"] = ratio
    assert assess(commercial_value=data).recency_factor_candidate == ratio


def timing(**changes):
    return component(buyer_key="buyer:1", offer_key="offer:1",
                     need_from="2026-10-01T12:00:00Z", need_until="2026-10-02T12:00:00Z",
                     capacity_from="2026-10-01T12:00:00Z", capacity_until="2026-10-02T12:00:00Z",
                     **changes)


@pytest.mark.parametrize("updates,need,overlap", [
    ({}, "OPEN", "OPEN"),
    ({"need_from": "2026-10-01T13:00:00Z"}, "FUTURE", "FUTURE"),
    ({"need_from": "2026-09-30T12:00:00Z", "need_until": "2026-10-01T12:00:00Z"}, "CLOSED", "NONE"),
    ({"need_from": None}, "UNKNOWN", "UNKNOWN"),
    ({"need_from": "2026-10-02T12:00:00Z", "need_until": "2026-10-03T12:00:00Z"}, "FUTURE", "NONE"),
])
def test_buyer_windows_are_separate_from_owned_inventory(updates, need, overlap):
    data = timing()
    data.update(updates)
    result = assess(buyer_timing=data, buyer_need_until="2000-01-01T00:00:00Z",
                    capacity_until="2000-01-01T00:00:00Z")
    assert result.state == "ACTIVE"
    assert result.expired_fields == ()
    assert result.buyer_timing["need"]["state"] == need
    assert result.buyer_timing["overlap"] == overlap
    assert result.recency_factor_candidate is None


@pytest.mark.parametrize("capacity,state", [(0, "FULL"), (None, "UNKNOWN"), (2, "AVAILABLE")])
def test_capacity_zero_is_distinct_from_missing(capacity, state):
    assert assess(buyer_timing=timing(available_capacity=capacity)).buyer_timing["capacity_availability"] == state


@pytest.mark.parametrize("field,value", [("buyer_key", ""), ("offer_key", ""), ("available_capacity", -1)])
def test_buyer_scope_and_capacity_validation(field, value):
    data = timing()
    data[field] = value
    assert assess(buyer_timing=data).buyer_timing["state"] == "UNKNOWN"


def saturation(**changes):
    return component(market_key="market:1", offer_key="offer:1", sample_definition="observed permits",
                     sample_size=10, contested_count=0, **changes)


def test_zero_contested_is_known_only_for_sample_and_has_no_penalty():
    result = assess(competitive_saturation=saturation())
    assert result.competitive_saturation["observed_contested_fraction"] == 0
    assert result.competitive_saturation["sample_definition"] == "observed permits"
    assert result.competitive_saturation["saturation_penalty"] is None
    assert result.recency_factor_candidate is None


@pytest.mark.parametrize("field,value", [("sample_size", 0), ("sample_size", True),
    ("contested_count", 11), ("contested_count", -1), ("contested_count", 0.5),
    ("sample_definition", ""), ("market_key", None), ("offer_key", ""),
    ("source_expires_at", "2026-10-01T12:00:00Z")])
def test_saturation_denominator_scope_and_validity(field, value):
    data = saturation()
    data[field] = value
    assert assess(competitive_saturation=data).competitive_saturation["state"] == "UNKNOWN"


def test_scope_disagreement_and_opportunity_mismatch_fail_closed():
    assert assess(offer_key="offer:other", buyer_timing=timing()).buyer_timing["state"] == "UNKNOWN"
    result = assess_opportunity_decay({"opportunity_key": "wrong", "commercial_value": commercial()},
                                      as_of=NOW, expected_opportunity_key="permit:1")
    assert result.state == "UNKNOWN"
    assert result.recency_factor_candidate is None


def test_naive_clock_rejected_and_freshness_boundary_stale():
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_opportunity_decay({}, as_of=NOW.replace(tzinfo=None))
    result = assess(observed_at="2026-10-01T11:00:00Z", freshness_window_seconds=3600)
    assert result.state == "STALE"
    assert result.stale_by_seconds == 0


@pytest.mark.parametrize("value", [[], "bad", 42, {"observed_at": []}])
def test_malformed_components_are_contained(value):
    result = assess(commercial_value=value, buyer_timing=value, competitive_saturation=value)
    assert all(getattr(result, name)["state"] == "UNKNOWN" for name in
               ("commercial_value", "buyer_timing", "competitive_saturation"))
