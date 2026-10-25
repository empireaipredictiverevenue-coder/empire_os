"""V4.21 continuation: signed, two-way bank/ledger reconciliation, HELD."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import UUID
from pathlib import Path
import runpy
import pytest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v421_dual_entry import (
    SCHEMA,reconcile_v421_bilateral_cash_held,
    review_v421_two_way_forecast_residuals_held,_canonical_signature_message,
)

ROOT=Path(__file__).resolve().parents[1]
V418=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v418_opportunities_20261025.py"))
SIGNED=V418["SIGNED"]
TWIN=V418["TWIN"]
TENANT=V418["TENANT"]
OTHER=V418["OTHER"]
NOW=datetime.now(timezone.utc)
BUYER="11111111-1111-4111-8111-111111111111"
O1="10000000-0000-4000-8000-000000000001"
O2="10000000-0000-4000-8000-000000000002"
O3="10000000-0000-4000-8000-000000000003"
BANK="fixture_issuer"
BUYER_PRIV=Ed25519PrivateKey.from_private_bytes(bytes([1])*32)
BANK_PRIV=Ed25519PrivateKey.from_private_bytes(bytes([2])*32)


def pub(k):
    return k.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def signed(payload,key):
    p=dict(payload)
    p["signature_hex"]=key.sign(_canonical_signature_message(p)).hex()
    return p


def fixtures():
    accepted=(NOW-timedelta(days=140)).isoformat()
    def order(ident,gross,cost):
        return {
            "order_id":ident,"opportunity_id":str(UUID(int=100+len(ident)+gross)),
            "tenant_id":TENANT,"buyer_id":BUYER,"currency_code":"USD",
            "gross_minor":gross,"acquisition_cost_minor":cost,
            "accepted_at":accepted,"source_evidence_digest":"a"*64,
        }
    orders=(order(O1,15000,1000),order(O2,7000,300))
    def advice(advice_id,order_id,amt):
        return signed({
            "advice_id":advice_id,"order_id":order_id,"tenant_id":TENANT,
            "buyer_id":BUYER,"currency_code":"USD","amount_minor":amt,
            "issued_at":(NOW-timedelta(days=139)).isoformat(),
            "evidence_digest":"b"*64,
        },BUYER_PRIV)
    advices=(
        advice("20000000-0000-4000-8000-000000000001",O1,15000),
        advice("20000000-0000-4000-8000-000000000002",O2,7000),
    )
    def event(i,order_id,amt,direction,days_after):
        return signed({
            "event_id":f"30000000-0000-4000-8000-{i:012d}",
            "order_id":order_id,"tenant_id":TENANT,
            "currency_code":"USD","amount_minor":amt,
            "direction":direction,
            "cleared_at":(NOW-timedelta(days=140-days_after)).isoformat(),
            "issuer_id":BANK,"evidence_digest":"c"*64,
        },BANK_PRIV)
    events=(
        event(1,O1,10000,"CREDIT",5),
        event(2,O1,5000,"CREDIT",15),
        event(3,O1,2000,"DEBIT",40),
        event(4,O2,6500,"CREDIT",10),
        event(5,O3,999,"CREDIT",10),
    )
    return orders,advices,events


def review(orders=None,advices=None,bank=None,**overrides):
    standard=fixtures()
    verifier,token=SIGNED()
    params={
        "research_twin":TWIN(),"signed_crm_bearer":token,
        "crm_verifier":verifier,
        "original_order_snapshots":standard[0] if orders is None else orders,
        "buyer_remittance_advices":standard[1] if advices is None else advices,
        "external_bank_events":standard[2] if bank is None else bank,
        "pinned_buyer_keys":{BUYER:pub(BUYER_PRIV)},
        "pinned_bank_keys":{BANK:pub(BANK_PRIV)},
        "as_of":NOW,
    }
    params.update(overrides)
    return reconcile_v421_bilateral_cash_held(**params)


def test_dual_entry_spot_missing_and_orphan_transactions():
    result=review()
    assert result["schema_version"]==SCHEMA
    assert result["order_rows_selected"]==2
    assert result["buyer_advice_rows_selected"]==2
    assert result["external_bank_events_selected"]==5
    assert result["matched_order_claims"]==1
    assert result["orders_with_discrepancy"]==1
    assert result["orders_with_missing_bank_credit"]==0
    assert result["orphan_external_order_references"]==1
    assert result["orphan_external_credit_events"]==1
    assert result["claimed_gross_credit_minor"]==21500
    assert result["claimed_refund_or_clawback_minor"]==2000
    assert result["claimed_acquisition_cost_minor"]==1300
    assert result["illustrative_net_minor"]==18200
    assert result["all_supplied_claims_reconciled"] is False
    assert result["actual_realised_net_cash_minor"] is None
    assert result["training_examples_eligible"]==0
    assert result["model_weights_updated"] is False
    assert result["execution_authority"]=="none"


def test_dual_entry_30_60_90_censored_and_refund_maturation():
    result=review()
    horizons=result["horizons"]
    assert [h["horizon_days"] for h in horizons]==[30,60,90]
    assert [h["illustrative_net_within_horizon_minor"] for h in horizons]==[
        20200,18200,18200,
    ]
    assert all(h["bank_verified_cash_minor"] is None for h in horizons)
    orders,advices,bank=fixtures()
    orders=tuple(dict(o,accepted_at=(NOW-timedelta(days=40)).isoformat())
                 for o in orders)
    # Timestamp disagreement becomes order-level mismatch, not 'bank settled'.
    censored=review(orders=orders)
    assert censored["horizons"][0]["all_selected_orders_mature"] is True
    assert censored["horizons"][1]["illustrative_net_within_horizon_minor"] is None
    assert censored["horizons"][2]["illustrative_net_within_horizon_minor"] is None


def test_dual_entry_full_signed_claims_still_not_trusted_bank_ground_truth():
    orders,advices,bank=fixtures()
    bank=tuple(e for e in bank if e["order_id"]!=O3)
    bank=list(bank)
    bank[3]=signed({**{k:v for k,v in bank[3].items() if k!="signature_hex"},
                    "amount_minor":7000},BANK_PRIV)
    result=review(bank=tuple(bank))
    assert result["all_supplied_claims_reconciled"] is True
    assert result["matched_order_claims"]==2
    assert result["external_bank_population_complete_verified"] is False
    assert result["actual_bank_settlement_independently_verified"] is False
    assert result["caller_pinned_key_authority_independently_verified"] is False
    assert result["production_calibration_authorized"] is False


@pytest.mark.parametrize("kind",["buyer","bank","issuer"])
def test_dual_entry_invalid_signature_or_issuer_rejected(kind):
    o,a,b=fixtures()
    if kind=="buyer":
        a=list(a);a[0]=dict(a[0],amount_minor=15001)
    if kind=="bank":
        b=list(b);b[0]=dict(b[0],amount_minor=12000)
    if kind=="issuer":
        b=list(b);b[0]=dict(b[0],issuer_id="imposter")
    with pytest.raises(ValueError,match="(SIGNATURE|ISSUER)"):
        review(advices=tuple(a),bank=tuple(b))


@pytest.mark.parametrize("kind",["order","advice","cash"])
def test_dual_entry_deduplicate_all_ledger_identity_events(kind):
    o,a,b=fixtures()
    if kind=="order":o=o+(o[0],)
    if kind=="advice":a=a+(a[0],)
    if kind=="cash":b=b+(b[0],)
    with pytest.raises(ValueError,match="DUPLICATE"):
        review(orders=o,advices=a,bank=b)


def test_dual_entry_wrong_tenant_and_currency_denied():
    o,a,b=fixtures()
    with pytest.raises(ValueError,match="CROSS_TENANT"):
        review(orders=(dict(o[0],tenant_id=OTHER),)+o[1:])
    with pytest.raises(ValueError,match="MIXED_CURRENCY"):
        review(bank=(dict(b[0],currency_code="GBP"),)+b[1:])
    model=TWIN();model["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="CROSS_TENANT"):
        review(research_twin=model)


def test_dual_entry_foreign_receipt_without_internal_order_is_counted():
    o,a,b=fixtures()
    report=review(orders=(o[0],),advices=(a[0],),bank=b)
    assert report["orphan_external_order_references"]==2
    assert report["orphan_external_credit_events"]==2
    assert report["all_supplied_claims_reconciled"] is False


def test_dual_entry_refund_exceeds_settlement_is_discrepancy():
    o,a,b=fixtures()
    bigger=list(b)
    bigger[2]=signed({**{k:v for k,v in b[2].items() if k!="signature_hex"},
                      "amount_minor":18000},BANK_PRIV)
    report=review(bank=tuple(bigger))
    assert report["refunds_exceed_credit_orders"]==1
    assert report["matched_order_claims"]==0
    assert report["production_calibration_authorized"] is False


def test_dual_entry_zero_bank_receipts_does_not_promote_unknown_to_zero_cash():
    o,a,b=fixtures()
    report=review(bank=())
    assert report["orders_with_missing_bank_credit"]==2
    assert report["all_supplied_claims_reconciled"] is False
    assert report["actual_realised_net_cash_minor"] is None
    assert report["training_examples_eligible"]==0


def test_dual_entry_empty_or_invalid_key_inventory_rejected():
    with pytest.raises(ValueError,match="PINNED_ISSUER"):
        review(pinned_bank_keys={})
    with pytest.raises(ValueError,match="PUBLIC_KEY"):
        review(pinned_bank_keys={BANK:b"abc"})


def test_dual_entry_manifests_do_not_mutate_production_subsystems():
    src=(ROOT/"empire_os/predictive_revenue_v421_dual_entry.py").read_text()
    for term in ("psycopg.connect(","CREATE TABLE ","INSERT INTO ",
                 "execute_payment(", "model.fit(", "send_email(",
                 "systemctl", "redis.Redis("):
        assert term not in src


def test_dual_entry_reverse_flow_before_first_credit_is_not_settlement():
    o,a,b=fixtures()
    altered=list(b)
    revised={k:v for k,v in b[2].items() if k!="signature_hex"}
    revised["cleared_at"]=(NOW-timedelta(days=138)).isoformat()
    altered[2]=signed(revised,BANK_PRIV)
    result=review(bank=tuple(altered))
    assert result["matched_order_claims"]==0
    assert result["orders_with_discrepancy"]==2
    assert result["production_calibration_authorized"] is False


def test_dual_entry_future_cutoff_cannot_mature_predictions():
    with pytest.raises(ValueError,match="FUTURE_EVIDENCE_CUTOFF"):
        review(as_of=NOW+timedelta(days=100))


def test_dual_entry_same_pinned_public_key_cannot_impersonate_buyer_and_bank():
    with pytest.raises(ValueError,match="MUST_BE_SEPARATE"):
        review(pinned_bank_keys={BANK:pub(BUYER_PRIV)})


def test_dual_entry_future_clearing_event_denied():
    o,a,b=fixtures()
    events=list(b)
    new={k:v for k,v in events[0].items() if k!="signature_hex"}
    new["cleared_at"]=(NOW+timedelta(days=1)).isoformat()
    events[0]=signed(new,BANK_PRIV)
    with pytest.raises(ValueError,match="FUTURE_BANK_TRANSACTION"):
        review(bank=tuple(events))


def sample_frozen_forecasts(manifest):
    locked=(NOW-timedelta(days=141)).isoformat()
    return tuple({
        "horizon_days":days,
        "forecast_net_minor":forecast,
        "locked_at":locked,
        "reconciliation_manifest_digest":manifest["source_manifest_digest_not_bank_proof"],
    } for days,forecast in ((30,20000),(60,19500),(90,18000)))


def evaluate_residual(recon=None,forecasts=None):
    reconcile=recon or review()
    rows=sample_frozen_forecasts(reconcile) if forecasts is None else forecasts
    verifier,bearer=SIGNED()
    return review_v421_two_way_forecast_residuals_held(
        claimed_reconciliation=reconcile,frozen_forecasts=rows,
        research_twin=TWIN(),signed_crm_bearer=bearer,
        crm_verifier=verifier,
    )


def test_dual_entry_30_60_90_residual_bridge_is_not_retraining():
    compared=evaluate_residual()
    assert [x["claimed_residual_minor"] for x in compared["horizons"]]==[
        200, -1300,200,
    ]
    assert compared["cash_ground_truth_verified"] is False
    assert compared["historical_learning_eligible"] is False
    assert compared["model_weights_updated"] is False
    assert compared["production_forecasting_authorized"] is False
    assert compared["execution_authority"]=="none"


def test_dual_entry_frozen_forecasts_cannot_be_post_hoc():
    reconciliation=review()
    rows=list(sample_frozen_forecasts(reconciliation))
    rows[0]=dict(rows[0],locked_at=NOW.isoformat())
    with pytest.raises(ValueError,match="FROZEN_BEFORE_COHORT"):
        evaluate_residual(recon=reconciliation,forecasts=tuple(rows))


def test_dual_entry_residuals_require_all_three_horizons_and_exact_manifest():
    recon=review()
    rows=sample_frozen_forecasts(recon)
    with pytest.raises(ValueError,match="THREE_LOCKED_HORIZON"):
        evaluate_residual(recon=recon,forecasts=rows[:2])
    with pytest.raises(ValueError,match="UNIQUE_30_60_90"):
        evaluate_residual(recon=recon,forecasts=(rows[0],rows[0],rows[2]))
    forged=list(rows)
    forged[0]=dict(forged[0],reconciliation_manifest_digest="f"*64)
    with pytest.raises(ValueError,match="FROZEN_BEFORE_COHORT"):
        evaluate_residual(recon=recon,forecasts=tuple(forged))


def test_dual_entry_unmatured_horizon_stays_null_not_zero_residual():
    orders,_,_=fixtures()
    recent=tuple(dict(o,accepted_at=(NOW-timedelta(days=40)).isoformat())
                 for o in orders)
    result=review(orders=recent)
    evaluation=evaluate_residual(recon=result,forecasts=sample_frozen_forecasts(result))
    assert evaluation["horizons"][0]["claimed_residual_minor"] is not None
    assert evaluation["horizons"][1]["claimed_residual_minor"] is None
    assert evaluation["horizons"][2]["claimed_residual_minor"] is None


def test_dual_entry_cannot_forge_verified_cash_in_bridge():
    report=review()
    forged=dict(report,actual_realised_net_cash_minor=100000)
    with pytest.raises(ValueError,match="NONPROMOTABLE"):
        evaluate_residual(recon=forged)
    forged=dict(report)
    forged["horizons"]=[dict(x) for x in report["horizons"]]
    forged["horizons"][0]["bank_verified_cash_minor"]=2500
    with pytest.raises(ValueError,match="FORGED_BANK_AUTHORITY"):
        evaluate_residual(recon=forged)
