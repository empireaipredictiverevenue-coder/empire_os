"""Original profit forecast must be declared prospectively, never retrofitted."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from test_predictive_four_stage_economic_custody import packets, check, NOW
from test_predictive_profitability_playbooks import plan
from empire_os.predictive_original_profit_forecast_preflight import (
    prepare_original_profit_forecast_preflight,
)


def run(p=None,e=None,c=None,at=NOW):
    if p is None:
        p=packets()[0]
    return prepare_original_profit_forecast_preflight(
        p,e if e is not None else plan(p),
        c if c is not None else check(),
        as_of=at,
    )


def test_original_profit_forecast_intent_does_not_register_or_claim_paid_profit():
    out=run()
    assert out["status"]=="PROSPECTIVE_PROFIT_FORECAST_SOURCE_DECLARATION_UNREGISTERED"
    assert len(out["original_intended_forecast_sha256"])==64
    payload=out["proposed_original_profit_forecast"]
    assert payload["forecast_kind"]=="scenario_weighted_operating_profit_research"
    assert payload["hypothetical_weighted_operating_profit_minor"]==360250
    assert payload["hypothetical_worst_operating_profit_minor"]==-179000
    assert payload["currency"]=="USD"
    assert payload["source_material_cost_minor_claimed"]==4000
    assert payload["source_labor_delivery_cost_minor_assumed"]==3750
    assert payload["source_unit_contribution_minor_unverified"]==4250
    assert payload["scenario_probabilities_calibrated"] is False
    assert out["original_profit_forecast_registry_target"]=="MISSING_DEDICATED_PROFIT_FORECAST_OWNER_REGISTRY"
    assert out["existing_conversion_probability_registry_is_suitable_profit_registry"] is False
    assert out["original_forecast_durably_registered"] is False
    assert out["original_profit_forecast_error_minor"] is None
    assert out["actual_profit_outcome_minor"] is None
    assert out["forecast_sent_or_registered"] is False
    assert out["database_writes"] is False
    assert out["execution_authority"]=="none"


def test_same_inputs_original_time_give_deterministic_reference():
    a=run()
    b=run()
    assert a["original_intended_forecast_sha256"]==b["original_intended_forecast_sha256"]
    assert a["proposed_original_profit_forecast"]==b["proposed_original_profit_forecast"]


def test_change_hypothetical_unit_economics_changes_forecast_intention_revision():
    p=packets()[0]
    params=plan(p)
    altered=deepcopy(params)
    altered["scenarios"][1]["unit_price_minor"]=13500
    a=run(p=p,e=params)
    b=run(p=p,e=altered)
    assert a["original_intended_forecast_sha256"]!=b["original_intended_forecast_sha256"]
    assert a["proposed_original_profit_forecast"]["hypothetical_weighted_operating_profit_minor"]!=(
        b["proposed_original_profit_forecast"]["hypothetical_weighted_operating_profit_minor"])


def test_missed_original_pilot_start_blocks_backfilled_profitable_looking_forecast():
    p=packets()[0]
    at=NOW+timedelta(days=5)
    with pytest.raises(ValueError):
        run(p=p,at=at)


@pytest.mark.parametrize("field,value",[
    ("original_opportunity_key","forged_different_opp"),
    ("original_pilot_design_sha256","f"*64),
    ("actual_revenue_minor",5000),
    ("actual_gross_profit_minor",1200),
    ("original_registered_before_outcome_forecast_authenticated",True),
    ("execution_authority","register"),
    ("database_writes",True),
    ("source_currency","GBP"),
])
def test_cannot_build_prospective_intent_from_fake_authenticated_profit(field,value):
    p=packets()[0]
    c=deepcopy(check())
    c[field]=value
    with pytest.raises(ValueError):
        run(p=p,c=c)


def test_forecast_is_not_existing_conversion_probability_registry():
    x=run()
    payload=x["proposed_original_profit_forecast"]
    assert payload["forecast_kind"]!="conversion_probability"
    assert x["independently_readback_prediction_verified"] is False
    assert x["original_registration_required_before_outcomes"] is True
    assert x["calibrated_profit_prediction_interval"] is None
    assert "external_customer_id" not in json.dumps(x)
