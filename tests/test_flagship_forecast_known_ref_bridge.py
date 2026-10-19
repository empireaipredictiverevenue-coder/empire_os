"""Read-only bridge safety tests; isolated fake reader, no real database."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from empire_os.flagship_forecast_known_ref_bridge import review_known_original_forecasts
from test_original_conversion_prediction_preflight import packet, NOW

TENANT = "test-tenant"
AT = NOW + timedelta(days=1)


def empty_memory():
    return {
        "schema_version": "empire.economic_memory.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "promoted_learning": False, "tenant_id": TENANT,
        "generated_at": NOW.isoformat(),
        "calibration_evidence": [], "verified_learning_feedback": [],
    }


def original_row():
    return deepcopy(packet()["proposed_prediction"])


def readback(row=None, recorded=None):
    row = row or original_row()
    digest = sha256(json.dumps(
        row, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()
    return {
        "prediction_ref": row["prediction_ref"],
        "tenant_id": row["tenant_id"],
        "prediction": row,
        "recorded_at": recorded or (NOW+timedelta(seconds=15)).isoformat(),
        "payload_sha256": digest,
    }


class FakeReader:
    def __init__(self, item):
        self.item = item
        self.calls = []

    def readback(self, *, tenant_id, prediction_ref):
        self.calls.append((tenant_id, prediction_ref))
        return deepcopy(self.item)


def review(reader, **kwargs):
    return review_known_original_forecasts(
        empty_memory(), tenant_id=TENANT,
        prediction_refs=[original_row()["prediction_ref"]],
        as_of=AT, reader=reader, **kwargs,
    )


def test_unapproved_read_only_reader_is_never_invoked():
    source = FakeReader(readback())
    result = review(source)
    assert result["status"] == "READ_ONLY_NOT_AUTHORISED"
    assert source.calls == []
    assert result["known_refs_matched"] is None
    assert result["database_writes"] is False


def test_existing_scoped_reader_is_reused_for_exact_known_ref():
    source = FakeReader(readback())
    result = review(source, approved_readonly=True)
    assert source.calls == [(TENANT, original_row()["prediction_ref"])]
    assert result["status"] == "KNOWN_REF_DESCRIPTIVE_RECONCILIATION_ONLY"
    assert result["known_refs_matched"] == 1
    assert result["known_refs_missing"] == 0
    assert result["known_refs_population_review"]["pending_before_horizon"] == 1
    assert result["known_refs_population_review"]["matched_terminal_win"] == 0
    assert result["complete_registry_population_verified"] is False
    assert result["authenticated_session_proven_by_bridge"] is False
    assert result["customer_accuracy_claim_authorized"] is False
    assert "prediction" not in result  # aggregates only


def test_missing_known_reference_is_not_a_verified_loss():
    source = FakeReader(None)
    result = review(source, approved_readonly=True)
    assert result["status"] == "KNOWN_REF_READBACK_INCOMPLETE"
    assert result["known_refs_missing"] == 1
    assert result["known_refs_population_review"] is None


def test_missing_reader_when_approved_fails_before_lookup():
    with pytest.raises(ValueError, match="reader"):
        review(None, approved_readonly=True)


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(tenant_id="other"),
    lambda x: x.update(payload_sha256="0"*64),
    lambda x: x["prediction"].update(predicted_probability=0.97),
    lambda x: x["prediction"].update(tenant_id="other"),
    lambda x: x["prediction"].update(prediction_ref="conversion_prediction_candidate:"+"f"*32),
    lambda x: x.update(recorded_at=(AT+timedelta(seconds=1)).isoformat()),
    lambda x: x.update(recorded_at=(NOW-timedelta(hours=1)).isoformat()),
    lambda x: x.update(extra_field=True),
])
def test_bad_readbacks_never_promote_calibration(mutate):
    source = readback()
    mutate(source)
    with pytest.raises(ValueError):
        review(FakeReader(source), approved_readonly=True)


def test_allowed_two_minute_prospective_clock_skew_matches_existing_registry():
    source = FakeReader(readback(recorded=(NOW-timedelta(seconds=60)).isoformat()))
    result = review(source, approved_readonly=True)
    assert result["known_refs_matched"] == 1
    assert result["customer_accuracy_claim_authorized"] is False


@pytest.mark.parametrize("refs", [
    ["wrong"],
    [original_row()["prediction_ref"]] * 2,
    [{}],
    [original_row()["prediction_ref"]] * 101,
])
def test_refs_must_be_explicit_bounded_and_unique(refs):
    reader = FakeReader(readback())
    with pytest.raises(ValueError):
        review_known_original_forecasts(
            empty_memory(), tenant_id=TENANT, prediction_refs=refs,
            as_of=AT, reader=reader, approved_readonly=True,
        )
    assert reader.calls == []


def test_cross_tenant_or_tampered_verified_memory_rejected_before_io():
    source = FakeReader(readback())
    m = empty_memory()
    m["tenant_id"] = "other"
    with pytest.raises(ValueError):
        review_known_original_forecasts(
            m, tenant_id=TENANT,
            prediction_refs=[original_row()["prediction_ref"]],
            as_of=AT, reader=source, approved_readonly=True,
        )
    assert source.calls == []
