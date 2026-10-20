"""Prospective Pilot -> Economics -> Commerce -> Customer Value -> Quant gate.

All sample source receipts are synthetic; matching source-owner dicts cannot
authenticate commerce, customer, forecast or actual profit.
"""
from copy import deepcopy
import json

import pytest

from test_predictive_customer_value_commerce_evidence import (
    original, event, report as commerce_review, TENANT, LATER, NOW,
)
from test_predictive_customer_value_measurement_evidence import (
    receipt, review as customer_value_review,
)
from test_predictive_profitability_playbooks import (
    plan as economic_plan,
)
from empire_os.predictive_profitability_playbooks import review_profitability_playbook
from test_original_conversion_registry import valid_review_material
from test_original_conversion_prediction_preflight import NOW as REGISTRY_NOW
from empire_os.original_conversion_registry import inspect_prospective_registry_readback
from empire_os.predictive_profit_outcome_instrument import review_profit_outcome_instrument


def build(*,empty=False):
    p=original()
    book=review_profitability_playbook(p,economic_plan(p),as_of=NOW)
    payments=commerce_review(
        [] if empty else [
            event(p,n=1,kind="service",life="booked",amount=0,cost=0),
            event(p,n=2,kind="service",life="paid",amount=18000,cost=4000),
            event(p,n=3,kind="service",life="refunded",transaction=1,amount=5000,
                  event_offset=14),
        ],pilot=p,
    )
    values=customer_value_review(
        [] if empty else [
            receipt(p,cohort="a",unique="a1",phase="baseline",value=100),
            receipt(p,cohort="a",unique="a2",phase="followup",value=220,days=12),
            receipt(p,cohort="b",unique="b1",arm="control",phase="baseline",value=120),
            receipt(p,cohort="b",unique="b2",arm="control",phase="followup",value=140,days=12),
        ],pilot=p,
    )
    candidate,receipt_data,readback=valid_review_material()
    registry=inspect_prospective_registry_readback(
        candidate,receipt=receipt_data,readback=readback,as_of=REGISTRY_NOW,
    )
    return p,book,payments,values,registry


def reviewed(data=None):
    return review_profit_outcome_instrument(
        *(data if data is not None else build()),as_of=LATER,
    )


def test_owner_claims_and_mocked_registry_are_research_not_profit():
    out=reviewed()
    assert out["status"]=="PROSPECTIVE_PROFIT_AND_CUSTOMER_VALUE_EVIDENCE_GATES_REVIEWED"
    assert len(out["original_pilot_design_revision_sha256"])==64
    assert out["registry_packet_status"]=="MATCHED_UNAUTHENTICATED_INPUT"
    assert out["registry_matching_dict_is_authenticated_db_attestation"] is False
    assert out["claimed_paid_event_count_not_verified_sales"]==1
    assert out["claimed_reversal_count_not_verified_refunds"]==1
    assert out["claimed_net_after_refunds_and_variable_cost_minor_unverified"]==9000
    assert out["claimed_paired_treatment_slots_unverified"]==1
    assert out["claimed_paired_control_slots_unverified"]==1
    assert out["claimed_control_comparison_delta_unverified_not_causal"]==100
    assert out["measured_gross_profit_minor"] is None
    assert out["measured_operating_profit_minor"] is None
    assert out["matched_original_forecast_and_outcome_pairs"] is None
    assert out["registered_original_profit_forecast_ref"] is None
    assert out["profit_prediction_error_minor"] is None
    assert out["conversion_brier_score"] is None
    assert len(out["remaining_measurement_proof_gates"])==7
    assert out["model_calibration_authorized"] is False
    assert out["economic_memory_outcome_written"] is False
    assert out["database_writes"] is False
    assert out["outbound_sent"] is False
    assert TENANT not in json.dumps(out)


def test_no_commerce_or_measurements_are_unknown_not_failed_sales():
    out=reviewed(build(empty=True))
    assert out["claimed_paid_event_count_not_verified_sales"]==0
    assert out["claimed_net_after_refunds_and_variable_cost_minor_unverified"] is None
    assert out["claimed_control_comparison_delta_unverified_not_causal"] is None
    assert out["profit_prediction_error_minor"] is None
    assert out["measured_cash_saved_minor"] is None


@pytest.mark.parametrize("index,field,value",[
    (0,"prospective_design_durably_registered",True),
    (0,"original_quant_forecast_registered",True),
    (1,"opportunity_key","other:market"),
    (1,"original_pilot_design_sha256","f"*64),
    (1,"original_forecast_registered",True),
    (1,"spend_authorized",True),
    (2,"source_owner_authentication_proven",True),
    (2,"original_pilot_design_revision_matched",False),
    (2,"tenant_authentication_proven",True),
    (2,"claimed_paid_event_count",True),
    (2,"source_reported_net_after_reversals_and_variable_cost_minor_unverified",float("nan")),
    (3,"original_quant_forecast_registered",True),
    (3,"original_pilot_revision_matched",False),
    (3,"source_owner_authenticated",True),
    (3,"causal_lift_verified",True),
    (3,"complete_control_pairs",-1),
    (3,"claimed_between_arm_delta_unverified_not_causal",float("inf")),
    (4,"original_prediction_registered",True),
    (4,"immutable_registry_proven",True),
    (4,"eligible_for_calibration",True),
    (4,"execution_authority","send"),
])
def test_false_authority_identity_or_impossible_metrics_rejected(index,field,value):
    parts=list(build())
    parts[index]=deepcopy(parts[index])
    parts[index][field]=value
    with pytest.raises(ValueError):
        reviewed(parts)


def test_registry_hold_is_not_model_failure_or_negative_conversion():
    packets=list(build())
    packets[4]=deepcopy(packets[4])
    packets[4].update(status="READBACK_HOLD",consistent=False)
    out=reviewed(packets)
    assert out["registry_packet_status"]=="READBACK_HOLD"
    assert out["matched_original_forecast_and_outcome_pairs"] is None
    assert out["conversion_brier_score"] is None


def test_commerce_claimed_paid_without_owner_gross_amount_rejected():
    packets=list(build())
    packets[2]=deepcopy(packets[2])
    packets[2]["source_reported_gross_minor_unverified"]=None
    with pytest.raises(ValueError):
        reviewed(packets)
