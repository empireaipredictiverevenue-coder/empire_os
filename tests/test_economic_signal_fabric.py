from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from empire_os.economic_signal_fabric import (
    EconomicSignalError,
    normalize_economic_signals,
    validate_economic_signal,
)


NOW = datetime(2026, 10, 6, 9, 30, tzinfo=timezone.utc)
TENANT = "tenant-alpha"


def row(**overrides):
    base = {
        "tenant_id": TENANT,
        "tenant_binding_ref": "canonical:tenant-binding:tenant-alpha:entity-1",
        "entity_id": str(uuid4()),
        "source_id": str(uuid4()),
        "signal_type": "market_gap",
        "signal_domain": "economic_opportunity",
        "observed_at": (NOW - timedelta(minutes=5)).isoformat(),
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
        "strength": 0.8,
        "confidence": 0.9,
        "evidence_refs": ["canonical:evidence:1"],
        "payload": {"market": "roofing:denver"},
        "truth_class": "OBSERVED",
        "data_backend": "empiredb",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("signal_type", [
    "revenue_leak",
    "idle_asset",
    "market_gap",
    "idle_waste",
])
def test_supported_economic_signal_types(signal_type):
    signal = validate_economic_signal(
        row(signal_type=signal_type),
        expected_tenant_id=TENANT,
        as_of=NOW,
    )
    assert signal.signal_type == signal_type
    assert signal.as_dict()["execution_authority"] == "none"


def test_tenant_id_without_binding_is_not_provenance():
    with pytest.raises(
        EconomicSignalError,
        match="verified_tenant_binding_required",
    ):
        validate_economic_signal(
            row(tenant_binding_ref=None),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_cross_tenant_signal_rejected():
    with pytest.raises(EconomicSignalError, match="tenant_mismatch"):
        validate_economic_signal(
            row(tenant_id="tenant-other"),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


@pytest.mark.parametrize("field", ["entity_id", "source_id"])
def test_canonical_uuid_identity_required(field):
    with pytest.raises(EconomicSignalError):
        validate_economic_signal(
            row(**{field: "not-a-uuid"}),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_stale_signal_rejected():
    with pytest.raises(EconomicSignalError, match="stale_observation"):
        validate_economic_signal(
            row(observed_at=(NOW - timedelta(days=2)).isoformat()),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_future_signal_rejected():
    with pytest.raises(
        EconomicSignalError,
        match="future_observation_rejected",
    ):
        validate_economic_signal(
            row(observed_at=(NOW + timedelta(seconds=1)).isoformat()),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


@pytest.mark.parametrize("value", [
    True,
    False,
    -0.1,
    1.1,
    float("inf"),
    float("nan"),
    "0.8",
])
def test_invalid_strength_rejected(value):
    with pytest.raises(EconomicSignalError, match="invalid_strength"):
        validate_economic_signal(
            row(strength=value),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_expired_signal_rejected():
    with pytest.raises(EconomicSignalError, match="expired_signal"):
        validate_economic_signal(
            row(expires_at=(NOW - timedelta(seconds=1)).isoformat()),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_missing_evidence_rejected():
    with pytest.raises(
        EconomicSignalError,
        match="evidence_refs_required",
    ):
        validate_economic_signal(
            row(evidence_refs=[]),
            expected_tenant_id=TENANT,
            as_of=NOW,
        )


def test_duplicate_signal_collapses_deterministically():
    original = row()
    duplicate = deepcopy(original)

    result = normalize_economic_signals(
        [original, duplicate],
        expected_tenant_id=TENANT,
        as_of=NOW,
    )

    assert result["accepted_count"] == 1
    assert result["conflict_count"] == 0


def test_same_identity_conflicting_payload_is_quarantined():
    original = row()
    changed = deepcopy(original)
    changed["payload"] = {"market": "different"}

    result = normalize_economic_signals(
        [original, changed],
        expected_tenant_id=TENANT,
        as_of=NOW,
    )

    assert result["accepted_count"] == 0
    assert result["conflict_count"] == 1


def test_malformed_record_does_not_poison_batch():
    good = row()
    bad = row(tenant_binding_ref=None)

    result = normalize_economic_signals(
        [bad, good],
        expected_tenant_id=TENANT,
        as_of=NOW,
    )

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1


def test_all_authorities_remain_none():
    signal = validate_economic_signal(
        row(),
        expected_tenant_id=TENANT,
        as_of=NOW,
    ).as_dict()

    for field in (
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert signal[field] == "none"
