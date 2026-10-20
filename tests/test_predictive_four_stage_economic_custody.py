"""Four original-owner lanes, one product/cohort, no synthetic paid claims."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from test_predictive_customer_value_commerce_evidence import (
    original, NOW, LATER, report as commerce_report, event,
)
from empire_os.predictive_calibration import prepare_prospective_conversion_prediction
from empire_os.predictive_four_stage_economic_custody import (
    review_four_stage_cost_price_forecast_custody,
)

TENANT=sha256(b"synthetic-finance-tenant").hexdigest()
SKU=sha256(b"synthetic-service-sku").hexdigest()


def h(value):
    return sha256(value.encode()).hexdigest()


def base(p=None,kind="materials"):
    p=p or original()
    return {
        "schema_version":f"empire.predictive_revenue.{kind}_owner_claim.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "source_owner":{
            "materials":"existing_materials_procurement",
            "operations":"existing_workforce_fulfilment",
            "selling_price":"existing_commercial_terms_billing",
        }[kind],
        "evidence_status":"SOURCE_OWNER_REPORTED_UNAUTHENTICATED",
        "generated_at":NOW.isoformat(),"tenant_ref_sha256":TENANT,
        "opportunity_key":p["opportunity_key"],
        "pilot_design_sha256":p["design_revision_sha256"],
        "product_ref_sha256":SKU,"geography_key":"little_rock_ar",
        "currency":"USD",
    }


def line(name,n=1,kind="supplier_quote",total=6000,units=2):
    return {
        "line_ref_sha256":h(name),"source_document_sha256":h("doc"+name),
        "document_kind":kind,"source_document_at":NOW.isoformat(),
        "units_allocated":units,"total_allocated_cost_minor":total,
        "cost_nature":"materials",
        "original_document_authenticated":False,
    }


def packets():
    p=original()
    mats=base(p,"materials")
    mats["line_items"]=[
        line("roof_shingle",total=6000),
        line("packaging",total=2000),
    ]
    ops=base(p,"operations")
    ops.update({
        "crew_minutes_per_unit":90,
        "assumed_hourly_loaded_labor_cost_minor":2000,
        "distance_tenths_km_per_unit":125,
        "assumed_delivery_cost_minor_per_km":40,
        "other_fulfilment_minor_per_unit":250,
        "capacity_units_source_verified":False,
    })
    price=base(p,"selling_price")
    price.update({
        "commercial_terms_sha256":h("commercial_terms"),
        "price_event_sha256":h("offer_event"),
        "price_observed_at":NOW.isoformat(),
        "price_state":"accepted_reported",
        "offered_unit_price_minor":12000,
        "payment_settled_and_refund_final_verified":False,
    })
    return p,mats,ops,price


def check(parts=None,*,as_of=NOW,commerce=None,forecast=None,receipt=None,readback=None):
    p,m,o,s=parts or packets()
    return review_four_stage_cost_price_forecast_custody(
        p,m,o,s,commerce_owner_review=commerce,
        original_quant_candidate=forecast,
        registry_receipt=receipt,registry_readback=readback,
        as_of=as_of,
    )


def forecast(p):
    return prepare_prospective_conversion_prediction(
        tenant_id="synthetic-quant-tenant",
        opportunity_key=p["opportunity_key"],
        predicted_probability=0.3,
        predicted_at=NOW.isoformat(),
        horizon_until=(NOW+timedelta(days=14)).isoformat(),
        evidence_refs=["research:1"],
        model_name="quant_original",model_version="v1",
        assessed_at=NOW,
    )


def test_materials_labor_delivery_and_claimed_offer_are_same_cost_cohort():
    x=check()
    assert x["status"]=="FOUR_STAGE_ECONOMIC_SOURCE_CUSTODY_REVIEWED"
    assert x["material_supplier_quote_line_count"]==2
    assert x["material_supplier_invoice_line_count"]==0
    assert x["quote_cost_minor_per_unit_claimed"]==4000
    assert x["selected_material_reference_cost_minor_unverified"]==4000
    assert x["crew_minutes_per_unit_source_owner_claim"]==90
    assert x["estimated_labor_cost_minor_per_unit"]==3000
    assert x["estimated_delivery_minor_per_unit"]==500
    assert x["estimated_fulfilment_cost_minor_per_unit"]==3750
    assert x["source_reported_offered_price_minor_per_unit"]==12000
    assert x["unverified_all_in_cost_reference_minor_per_unit"]==7750
    assert x["illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead"]==4250
    assert x["illustrative_unit_contribution_margin_pct_unverified"]==35.41667
    assert x["raw_tenant_product_supplier_buyer_ids_disclosed"] is False
    assert x["actual_revenue_minor"] is None
    assert x["actual_gross_profit_minor"] is None
    assert x["economic_memory_training_authorized"] is False
    assert x["database_writes"] is False
    assert TENANT not in json.dumps(x) and SKU not in json.dumps(x)


def test_invoice_only_claim_not_signed_supplier_document():
    p,m,o,s=packets()
    m["line_items"]=[line("item_invoice",kind="supplier_invoice",total=9000,units=3)]
    x=check((p,m,o,s))
    assert x["invoice_cost_minor_per_unit_claimed"]==3000
    assert x["quote_cost_minor_per_unit_claimed"] is None
    assert x["selected_material_reference_cost_minor_unverified"]==3000
    assert x["source_cost_invoice_independently_authenticated"] is False
    assert x["actual_gross_profit_minor"] is None


def test_mixed_quote_and_invoice_never_double_spends_or_chooses_silent_version():
    p,m,o,s=packets()
    m["line_items"][1]["document_kind"]="supplier_invoice"
    x=check((p,m,o,s))
    assert x["quote_invoice_mix_blocks_single_cost_reference"] is True
    assert x["selected_material_reference_cost_minor_unverified"] is None
    assert x["unverified_all_in_cost_reference_minor_per_unit"] is None
    assert x["illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead"] is None


def test_negative_illustrative_margin_is_not_claimed_real_loss():
    p,m,o,s=packets()
    s["offered_unit_price_minor"]=3000
    x=check((p,m,o,s))
    assert x["illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead"]==-4750
    assert x["actual_gross_profit_minor"] is None


@pytest.mark.parametrize("which,field,value",[
    (1,"currency","GBP"),
    (1,"tenant_ref_sha256",h("different_tenant")),
    (1,"product_ref_sha256",h("new_service")),
    (1,"geography_key","new_york_ny"),
    (1,"pilot_design_sha256","f"*64),
    (1,"evidence_status","ACTUAL_VERIFIED_INVOICE"),
    (1,"execution_authority","spend"),
    (2,"product_ref_sha256",h("different_product")),
    (2,"currency","EUR"),
    (2,"capacity_units_source_verified",True),
    (2,"geography_key","seattle_wa"),
    (3,"product_ref_sha256",h("different_product")),
    (3,"payment_settled_and_refund_final_verified",True),
    (3,"price_state","paid_verified"),
    (3,"price_observed_at",(NOW+timedelta(days=30)).isoformat()),
    (3,"offered_unit_price_minor",True),
    (3,"offered_unit_price_minor",0),
    (3,"offered_unit_price_minor",-1),
    (3,"offered_unit_price_minor",1e8),
    (3,"geography_key","PRIVATE STREET ADDRESS"),
])
def test_cross_tenant_sku_currency_geo_and_false_financial_promotion_rejected(
    which,field,value,
):
    parts=list(packets())
    parts[which][field]=value
    with pytest.raises(ValueError):
        check(parts)


@pytest.mark.parametrize("field,value",[
    ("line_ref_sha256","not hash"),
    ("original_document_authenticated",True),
    ("units_allocated",0),("units_allocated",True),
    ("total_allocated_cost_minor",9001),
    ("total_allocated_cost_minor",-1),
    ("total_allocated_cost_minor",float("nan")),
    ("document_kind","settled"),
    ("source_document_at",(NOW+timedelta(days=1)).isoformat()),
])
def test_source_cost_doc_forgery_invalid_allocation_or_future_rejected(field,value):
    p,m,o,s=packets()
    m["line_items"][0][field]=value
    with pytest.raises(ValueError):
        check((p,m,o,s))


def test_duplicate_material_lines_or_unknown_source_field_rejected():
    p,m,o,s=packets()
    m["line_items"].append(deepcopy(m["line_items"][0]))
    with pytest.raises(ValueError):
        check((p,m,o,s))
    p,m,o,s=packets()
    m["fake_source_approval"]=True
    with pytest.raises(ValueError):
        check((p,m,o,s))


@pytest.mark.parametrize("field,value",[
    ("crew_minutes_per_unit",True),
    ("crew_minutes_per_unit",1_000_001),
    ("assumed_hourly_loaded_labor_cost_minor",-1),
    ("assumed_hourly_loaded_labor_cost_minor",1e3),
    ("distance_tenths_km_per_unit",True),
    ("assumed_delivery_cost_minor_per_km",float("nan")),
    ("other_fulfilment_minor_per_unit",-3),
])
def test_original_labor_delivery_parameters_must_be_exact_nonnegative_minor(field,value):
    p,m,o,s=packets()
    o[field]=value
    with pytest.raises(ValueError):
        check((p,m,o,s))


def test_fractional_crew_and_mileage_estimates_round_cost_up():
    p,m,o,s=packets()
    o.update(crew_minutes_per_unit=1,assumed_hourly_loaded_labor_cost_minor=101,
             distance_tenths_km_per_unit=1,assumed_delivery_cost_minor_per_km=11,
             other_fulfilment_minor_per_unit=0)
    x=check((p,m,o,s))
    assert x["estimated_labor_cost_minor_per_unit"]==2
    assert x["estimated_delivery_minor_per_unit"]==2


def test_existing_commerce_claims_reused_but_not_paid_unit_evidence():
    p,m,o,s=packets()
    ev=event(p,n=1,kind="service",life="paid",amount=12000,cost=2000)
    report=commerce_report([ev],pilot=p,as_of=LATER)
    x=check((p,m,o,s),commerce=report)
    assert x["commerce_claimed_paid_event_count_not_actual_paid_units"]==1
    assert x["source_reported_commerce_review_status"]=="OWNER_COMMERCE_CLAIMS_UNAUTHENTICATED_NOT_UNIT_JOINABLE"
    assert x["payment_settlement_refund_finality_verified"] is False
    assert x["actual_revenue_minor"] is None
    assert x["matched_original_profit_forecast_and_outcome_pairs"] is None


def test_mismatched_commerce_currency_refused():
    p,m,o,s=packets()
    report=commerce_report(
        [event(p,kind="service",life="paid",currency="GBP")],pilot=p,as_of=LATER)
    with pytest.raises(ValueError):
        check((p,m,o,s),commerce=report)


def test_original_quant_forecast_candidate_is_validated_but_never_registered():
    p,m,o,s=packets()
    f=forecast(p)
    x=check((p,m,o,s),forecast=f)
    assert x["original_quant_candidate_status"]=="CANDIDATE_VALIDATED_NOT_REGISTERED"
    assert x["original_quant_candidate_reference_not_registry_proof"]==f["candidate_prediction_ref"]
    assert x["quant_registry_has_original_pilot_sha256_and_tenant_digest_binding"] is False
    assert x["original_registered_before_outcome_forecast_authenticated"] is False
    assert x["original_forecast_profit_error_minor"] is None
    assert x["billing_or_commercial_actions_authorized"] is False


def test_quant_candidate_expiration_and_cross_market_opportunity_rejected():
    p,m,o,s=packets()
    with pytest.raises(ValueError):
        check((p,m,o,s),forecast=forecast(p),as_of=NOW+timedelta(minutes=6))
    candidate=prepare_prospective_conversion_prediction(
        tenant_id="synthetic-tenant",opportunity_key="different-opportunity",
        predicted_probability=0.15,predicted_at=NOW.isoformat(),
        horizon_until=(NOW+timedelta(days=14)).isoformat(),
        evidence_refs=["source:one"],model_name="quant",
        model_version="v2",assessed_at=NOW,
    )
    with pytest.raises(ValueError):
        check((p,m,o,s),forecast=candidate)


def test_mocked_quant_matching_receipt_does_not_authorise_forecast_training():
    p,m,o,s=packets()
    f=forecast(p)
    z=check((p,m,o,s),forecast=f,receipt={"status":"recorded"},readback={"status":"read"})
    assert z["original_quant_registry_readback_status"]=="READBACK_HOLD"
    assert z["original_registered_before_outcome_forecast_authenticated"] is False
    assert z["original_forecast_profit_error_minor"] is None


def test_forged_payment_in_commerce_snapshot_does_not_unlock_source_joins():
    p,m,o,s=packets()
    report=commerce_report([event(p,kind="service",life="paid")],pilot=p,as_of=LATER)
    report["source_owner_authentication_proven"]=True
    with pytest.raises(ValueError):
        check((p,m,o,s),commerce=report)


def test_expired_source_snapshots_no_longer_current_cost_estimate():
    with pytest.raises(ValueError):
        check(as_of=NOW+timedelta(days=4))
