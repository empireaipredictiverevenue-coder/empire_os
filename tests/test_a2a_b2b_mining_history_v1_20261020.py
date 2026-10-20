"""Longitudinal source coverage is not new buyers or disappearing market demand."""
from __future__ import annotations
from copy import deepcopy
import pytest

from empire_os.a2a_b2b_evidence_mining_v1 import (
    mine_targeted_business_evidence, make_mining_source_hold,
)
from empire_os.a2a_b2b_mining_history_v1 import update_mining_history
from tests.test_a2a_b2b_evidence_mining_v1_20261020 import fixture_data, NOW


def mining():
    return mine_targeted_business_evidence(*fixture_data(), now=NOW)


def test_identical_sources_are_one_mining_event_not_two_new_research_buys():
    first = mining()
    history = update_mining_history(first)
    second = update_mining_history(first, history)
    assert history["new_snapshot_appended"]
    assert history["snapshot_count"] == 1
    assert not second["new_snapshot_appended"]
    assert second["snapshot_count"] == 1
    assert second["snapshots"][0]["verified_real_leads"] == 0
    assert second["conversion_model_training_allowed"] is False
    assert second["verified_customer_contacts_stored"] is False


def test_owner_snapshot_rotation_is_new_source_coverage_not_lost_demand():
    initial = mining()
    history = update_mining_history(initial)
    data = list(fixture_data())
    data[2]["seeds"].pop()
    data[2]["seed_count"] -= 1
    revised = mine_targeted_business_evidence(*data, now=NOW)
    next_history = update_mining_history(revised, history)
    assert next_history["snapshot_count"] == 2
    assert next_history["changed_source_families"] == ["buyer_public_research_seeds"]
    assert next_history["owner_source_rotation_does_not_mean_demand_disappeared"]
    assert next_history["snapshots"][-1]["verified_new_buyers"] == 0


def test_cannot_infer_buyer_numbers_from_missing_sources():
    first = update_mining_history(mining())
    held = make_mining_source_hold(
        fixture_data()[0], reason="CANONICAL_MINING_INPUT_UNAVAILABLE", now=NOW)
    now = update_mining_history(held, first)
    assert not now["history_source_available"]
    assert now["snapshot_count"] == 1
    assert not now["new_snapshot_appended"]


def test_tampered_records_or_previous_snapshots_rejected():
    first = mining()
    forged = deepcopy(first)
    forged["verified_real_lead_count"] = 9
    with pytest.raises(ValueError, match="UNTRUSTED_MINING"):
        update_mining_history(forged)
    forged = deepcopy(first)
    forged["source_snapshot_digests_not_issuer_signatures"]["buyer_scout_research_window"] = "fake"
    with pytest.raises(ValueError, match="INVALID_MINING_SNAPSHOT_DIGESTS"):
        update_mining_history(forged)
    hist = update_mining_history(first)
    hist["snapshots"][0]["source_snapshot_digests"]["nyc_derived_permit_report"] = "bad"
    with pytest.raises(ValueError, match="INVALID_PREVIOUS"):
        update_mining_history(first, hist)
