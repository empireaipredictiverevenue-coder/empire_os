"""V17 scientific audit: no inference from single genesis or fake opportunities."""
from copy import deepcopy
from datetime import timedelta

import pytest

from empire_os.data_exchange_observation_custody import CustodyIntegrityError
from empire_os.data_exchange_scientific_custody_review import (
    build_scientific_custody_review,
)
from tests.test_data_exchange_temporal_quality import NOW, custody, snap


def review(*pairs,recheck=None):
    return build_scientific_custody_review(
        custody(*pairs),assessed_at=NOW,recheck=recheck)


def test_live_genesis_is_scientifically_inconclusive():
    report=review((NOW-timedelta(hours=1),"non-permissioned"))
    assert report["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert report["canonical_observation_count_in_window"]==1
    assert report["latest_pair_changed_entity_count"]==0
    assert report["latest_pair_unchanged_control_entity_count"]==0
    assert report["existing_agi_review_status"]=="NOT_RUN_REQUIRES_TWO_GENUINE_OBSERVATIONS"
    assert report["existing_agi_evidence_ref"] is None
    assert "NOT_ENOUGH_VERIFIED_TEMPORAL_EVIDENCE" in report["scientific_blockers"]
    assert report["claims"]["commercial_buyer_intent"]=="NOT_VERIFIED"
    assert report["model_inference_performed"] is False
    assert report["customer_delivery_enabled"] is False


def test_true_comparable_stable_pair_creates_unchanged_controls_not_buyers():
    older=NOW-timedelta(hours=51)
    later=NOW-timedelta(hours=25)
    report=review((older,"non-permissioned"),(later,"non-permissioned"),
                  recheck=snap(NOW-timedelta(minutes=1)))
    assert report["canonical_observation_count_in_window"]==2
    assert report["latest_pair_matched_entity_count"]==3
    assert report["latest_pair_unchanged_control_entity_count"]==3
    assert report["latest_pair_changed_entity_count"]==0
    assert report["existing_agi_review_status"]=="EXISTING_AGI_EVIDENCE_REVIEW_OBSERVE_ONLY"
    assert report["existing_agi_evidence_ref"].startswith("empire:construction_history:")
    assert report["v14_board_status"]=="NO_OBSERVED_FIELD_CHANGES"
    assert report["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert report["hypotheses_verified"] is False
    assert report["forecast_accuracy_verified"] is False
    assert report["commercial_revenue_verified"] is False


def test_real_field_change_is_internal_falsifiable_review_not_buyer_intent():
    older=NOW-timedelta(hours=51)
    later=NOW-timedelta(hours=25)
    report=review((older,"non-permissioned"),(later,"permissioned"),
                  recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert report["status"]=="INTERNAL_FALSIFIABLE_REVIEW_ONLY"
    assert report["latest_pair_changed_entity_count"]==3
    assert report["latest_pair_unchanged_control_entity_count"]==0
    assert report["v14_observed_field_changes_in_window"]==3
    assert report["existing_agi_research_workstreams"]
    assert report["existing_agi_review_status"]=="EXISTING_AGI_EVIDENCE_REVIEW_OBSERVE_ONLY"
    assert report["claims"]["historical_sample_comparison"]=="INTERNAL_DESCRIPTIVE_ONLY"
    assert report["claims"]["site_lifecycle_causality"]=="NOT_ESTABLISHED"
    assert report["buyer_intent_verified"] is False
    assert report["customer_delivery_enabled"] is False


def test_premature_two_snapshot_history_does_not_pass_temporal_readiness():
    older=NOW-timedelta(hours=4)
    later=NOW-timedelta(hours=3)
    report=review((older,"non-permissioned"),(later,"permissioned"))
    assert report["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert "LATEST_OBSERVATIONS_LESS_THAN_24H_APART" in report["scientific_blockers"]
    assert report["v14_observed_field_changes_in_window"]==3
    assert report["claims"]["historical_sample_comparison"]=="INSUFFICIENT_OR_HELD"


def test_same_source_recheck_is_not_independent_attestation():
    report=review((NOW-timedelta(hours=50),"non-permissioned"),
                  (NOW-timedelta(hours=25),"permissioned"),
                  recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert report["current_source_recheck"]=="REPEAT_SAME_SOURCE_MATCH"
    assert report["claims"]["government_attestation"]=="NOT_VERIFIED"
    assert report["external_anchor_verified"] is False
    assert report["independent_field_rights_review_completed"] is False
    assert "SOURCE_AUTHENTICITY_NOT_INDEPENDENTLY_ATTESTED" in report["scientific_blockers"]


@pytest.mark.parametrize("changed",[
    lambda r:r[0].update({"chain_sha256":"f"*64}),
    lambda r:r[0]["snapshot_json"]["records"][0].update({"email":"private@example.com"}),
    lambda r:r[0]["snapshot_json"].update({"data_resale_authorized":True}),
])
def test_tampered_canonical_custody_never_gets_science_report(changed):
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    altered=deepcopy(rows)
    changed(altered)
    with pytest.raises((CustodyIntegrityError,ValueError)):
        build_scientific_custody_review(altered,assessed_at=NOW)


def test_more_than_sixteen_rows_never_claim_full_genesis_proof():
    from empire_os.data_exchange_observation_custody import plan_custody_append
    previous=None
    full=[]
    for days_ago in range(17,0,-1):
        at=NOW-timedelta(days=days_ago)
        item=plan_custody_append(snap(at),previous=previous,assessed_at=NOW)["row"]
        full.append(item)
        previous=item
    result=build_scientific_custody_review(full[-16:],assessed_at=NOW)
    assert result["genesis_verified_in_window"] is False
    assert result["existing_agi_review_status"]=="HOLD_ROLLING_WINDOW_ORIGIN_NOT_REVALIDATED"
    assert "GENESIS_OUTSIDE_VERIFIED_READ_WINDOW" in result["scientific_blockers"]
    assert result["external_anchor_verified"] is False


def test_determinism_and_no_commercial_release():
    args=((NOW-timedelta(hours=50),"non-permissioned"),
          (NOW-timedelta(hours=25),"non-permissioned"))
    a=review(*args)
    b=review(*args)
    assert a==b
    assert a["data_resale_authorized"] is False
    assert a["payment_execution"] is False
    assert a["outbound_enabled"] is False
    assert a["production_writes"] is False
    assert a["execution_authority"]=="NONE"


def test_stale_pair_does_not_become_scientifically_ready():
    older=NOW-timedelta(days=7)
    later=NOW-timedelta(days=5)
    report=review((older,"non-permissioned"),(later,"permissioned"),
                  recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert report["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert report["temporal_quality_status"]=="HOLD_REVIEW_REQUIRED"
    assert report["existing_agi_review_status"]=="HOLD_TEMPORAL_EVIDENCE_NOT_READY_FOR_AGI"
    assert "LATEST_CANONICAL_OBSERVATION_OVER_72H_OLD" in report["scientific_blockers"]
    assert report["v14_observed_field_changes_in_window"]==3
    assert report["customer_delivery_enabled"] is False


def test_changed_live_recheck_blocks_scientific_ready_status():
    earlier=NOW-timedelta(hours=50)
    later=NOW-timedelta(hours=25)
    report=review((earlier,"non-permissioned"),(later,"permissioned"),
                  recheck=snap(NOW-timedelta(minutes=1),status="pending-decision"))
    assert report["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert report["current_source_recheck"]=="RECHECK_DIFFERS_FROM_STORED_SOURCE"
    assert "CURRENT_SOURCE_DIFFERS_REQUIRES_NEW_CANONICAL_OBSERVATION" in report["scientific_blockers"]
    assert report["buyer_intent_verified"] is False
