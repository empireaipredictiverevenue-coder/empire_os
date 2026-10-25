"""V4.21 independent finance proof gap + signed pre-outcome freeze custody tests."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json,runpy
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v421_forecast_custody import (
    SCHEMA,review_v421_forecast_freeze_held,
    review_v421_calibration_admission_held,
)
from empire_os.enterprise_finance_evidence_readiness import review_finance_source_readiness
from empire_os.predictive_revenue_v421_dual_entry import _canonical_signature_message

ROOT=Path(__file__).resolve().parents[1]
OLDER=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v421_statement_chain_20261025.py"))
SIGNED=OLDER["SIGNED"]
TWIN=OLDER["TWIN"]
TENANT=OLDER["TENANT"]
OTHER="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NOW=datetime.now(timezone.utc)
INCEPTION=NOW-timedelta(days=140)
COHORT="empire-v421-offline-cohort-001"
FORECAST_KEY=Ed25519PrivateKey.from_private_bytes(bytes([4])*32)
WITNESS_KEY=Ed25519PrivateKey.from_private_bytes(bytes([5])*32)


def signed(payload,key):
    return {**payload,"signature_hex":key.sign(
        _canonical_signature_message(payload)).hex()}


def pub(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def fixtures():
    forecasts=[]
    witnesses=[]
    for horizon in (30,60,90):
        frozen=signed({
            "tenant_id":TENANT,"source_evidence_digest":"a"*64,
            "currency_code":"USD","cohort_id":COHORT,
            "horizon_days":horizon,"forecast_net_minor":horizon*100,
            "locked_at":(INCEPTION-timedelta(days=2)).isoformat(),
        },FORECAST_KEY)
        witness=signed({
            "tenant_id":TENANT,"cohort_id":COHORT,
            "horizon_days":horizon,
            "forecast_sha256":sha256(json.dumps(
                frozen,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "witnessed_at":(INCEPTION-timedelta(days=1)).isoformat(),
            "sequence_no":10+horizon,
        },WITNESS_KEY)
        forecasts.append(frozen);witnesses.append(witness)
    return tuple(forecasts),tuple(witnesses)


def review(*,forecasts=None,witnesses=None,**overrides):
    original,detached=fixtures()
    verifier,bearer=SIGNED()
    kwargs={
        "research_twin":TWIN(),"signed_crm_bearer":bearer,
        "crm_verifier":verifier,
        "cohort_id":COHORT,
        "earliest_opportunity_at":INCEPTION,
        "frozen_forecasts":original if forecasts is None else forecasts,
        "timestamp_witnesses":detached if witnesses is None else witnesses,
        "pinned_forecast_signer":pub(FORECAST_KEY),
        "pinned_witness_signer":pub(WITNESS_KEY),
        "as_of":NOW,
    }
    kwargs.update(overrides)
    return review_v421_forecast_freeze_held(**kwargs)


def test_v421_frozen_forecast_signatures_pre_outcome_consistent_not_trusted():
    result=review()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V421_PRE_OUTCOME_SIGNED_CUSTODY_CLAIMS_ONLY_HELD"
    assert [x["horizon_days"] for x in result["horizons"]]==[30,60,90]
    assert result["signed_forecast_content_consistent"] is True
    assert result["independent_timestamp_authority_verified"] is False
    assert result["pre_outcome_forecast_lock_independently_proven"] is False
    assert result["realised_cash_ground_truth_minor"] is None
    assert result["production_model_weights_updated"] is False
    assert result["execution_authority"]=="none"


def test_v421_forecast_tampering_without_resign_is_denied():
    forecasts,witnesses=fixtures()
    forged=list(forecasts)
    forged[0]=dict(forged[0],forecast_net_minor=999999)
    with pytest.raises(ValueError,match="INVALID_DOCUMENT_SIGNATURE"):
        review(forecasts=tuple(forged))


def test_v421_forecast_resigned_but_witness_unmodified_is_denied():
    forecasts,witnesses=fixtures()
    new=list(forecasts)
    fields={k:v for k,v in forecasts[0].items() if k!="signature_hex"}
    new[0]=signed(dict(fields,forecast_net_minor=10000),FORECAST_KEY)
    with pytest.raises(ValueError,match="CONTENT_MISMATCH"):
        review(forecasts=tuple(new))


def test_v421_forecast_and_witness_both_resigned_after_start_is_denied():
    forecasts,witnesses=fixtures()
    new=list(forecasts)
    payload={k:v for k,v in forecasts[0].items() if k!="signature_hex"}
    payload["locked_at"]=(INCEPTION+timedelta(hours=1)).isoformat()
    new[0]=signed(payload,FORECAST_KEY)
    with pytest.raises(ValueError,match="LOCKED_AFTER_OPPORTUNITY"):
        review(forecasts=tuple(new))


def test_v421_witness_replayed_or_out_of_order_sequence_denied():
    forecasts,witnesses=fixtures()
    changed=list(witnesses)
    previous={k:v for k,v in witnesses[1].items() if k!="signature_hex"}
    previous["sequence_no"]=witnesses[0]["sequence_no"]
    changed[1]=signed(previous,WITNESS_KEY)
    with pytest.raises(ValueError,match="SEQUENCE_REPLAY"):
        review(witnesses=tuple(changed))


def test_v421_witness_signer_cannot_be_same_as_forecast_signer():
    with pytest.raises(ValueError,match="SEPARATE_ED25519"):
        review(pinned_witness_signer=pub(FORECAST_KEY))


def test_v421_bad_tenant_or_source_or_currency_fails_before_signature():
    forecasts,witnesses=fixtures()
    changed=list(forecasts)
    changed[0]=dict(changed[0],currency_code="GBP")
    with pytest.raises(ValueError,match="TENANT_SOURCE_CURRENCY"):
        review(forecasts=tuple(changed))
    changed[0]=dict(changed[0],tenant_id=OTHER)
    with pytest.raises(ValueError,match="TENANT_SOURCE_CURRENCY"):
        review(forecasts=tuple(changed))


def test_v421_witness_not_before_opportunity_denied():
    _,witnesses=fixtures()
    changed=list(witnesses)
    payload={k:v for k,v in witnesses[0].items() if k!="signature_hex"}
    payload["witnessed_at"]=(INCEPTION+timedelta(minutes=1)).isoformat()
    changed[0]=signed(payload,WITNESS_KEY)
    with pytest.raises(ValueError,match="NOT_OBSERVED_PRE_OUTCOME"):
        review(witnesses=tuple(changed))


def test_v421_bad_crm_membership_and_wrong_twin_tenant_fail():
    verifier,bearer=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_SIGNED_CRM"):
        review(crm_verifier=verifier,signed_crm_bearer=bearer+"tampered")
    twin=TWIN();twin["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_MISMATCH"):
        review(research_twin=twin)


def test_v421_live_finance_readiness_gaps_remain_visible(tmp_path):
    ready=review_finance_source_readiness(tmp_path)
    assert ready["required_proofs_not_admitted_count"]==7
    chain=OLDER["review"]()
    freeze=review()
    result=review_v421_calibration_admission_held(
        freeze_receipt=freeze,chain_receipt=chain,finance_readiness=ready)
    assert result["status"]=="V421_INDEPENDENT_CASH_CALIBRATION_EVIDENCE_NOT_ADMITTED"
    assert result["eligible_training_cohorts"]==0
    assert [x["horizon_days"] for x in result["horizons"]]==[30,60,90]
    assert all("INDEPENDENT_BANK_ISSUER_AND_ACCOUNT_NOT_ATTESTED" in
               x["unresolved_gate_codes"] for x in result["horizons"])
    assert all("UNRESOLVED_ORDER_OR_EXTERNAL_RECEIPT_MISMATCH" in
               x["unresolved_gate_codes"] for x in result["horizons"])
    assert result["verified_cvr_ecac_authorized"] is False
    assert result["production_forecast_calibration_authorized"] is False


def test_v421_forged_cash_claim_or_unapproved_trainer_rejected(tmp_path):
    finance=review_finance_source_readiness(tmp_path)
    chain=OLDER["review"]()
    forged=dict(chain,actual_realised_net_cash_minor=42)
    with pytest.raises(ValueError,match="ORIGINAL_HELD"):
        review_v421_calibration_admission_held(
            freeze_receipt=review(),chain_receipt=forged,finance_readiness=finance)
    forged=dict(finance,actual_recognised_revenue_independently_verified=True)
    with pytest.raises(ValueError,match="ORIGINAL_HELD"):
        review_v421_calibration_admission_held(
            freeze_receipt=review(),chain_receipt=chain,finance_readiness=forged)


def test_v421_duplicate_horizon_cannot_disguise_missing_forecast():
    original,_=fixtures()
    with pytest.raises(ValueError,match="DUPLICATE_OR_UNKNOWN_FORECAST_HORIZON"):
        review(forecasts=(original[0],original[0],original[2]))


def test_v421_wrong_witness_digest_or_signature_rejected():
    _,witnesses=fixtures()
    altered=list(witnesses)
    altered[0]=dict(altered[0],forecast_sha256="f"*64)
    with pytest.raises(ValueError,match="INVALID_DOCUMENT_SIGNATURE"):
        review(witnesses=tuple(altered))
    payload={k:v for k,v in witnesses[0].items() if k!="signature_hex"}
    payload["forecast_sha256"]="f"*64
    altered[0]=signed(payload,WITNESS_KEY)
    with pytest.raises(ValueError,match="CONTENT_MISMATCH"):
        review(witnesses=tuple(altered))


def test_v421_held_gate_rejects_forged_issuer_or_model_training(tmp_path):
    finance=review_finance_source_readiness(tmp_path)
    base=OLDER["review"]()
    frozen=review()
    for forged in (
        dict(base,issuer_public_key_independently_attested=True),
        dict(base,bank_statement_inventory_complete_verified=True),
        dict(base,refund_and_chargeback_finality_verified=True),
        dict(base,production_model_weights_updated=True),
        dict(base,training_samples_eligible=5),
    ):
        with pytest.raises(ValueError,match="ORIGINAL_HELD"):
            review_v421_calibration_admission_held(
                freeze_receipt=frozen,chain_receipt=forged,finance_readiness=finance)


def test_v421_real_readonly_inventory_requires_explicit_flag(tmp_path,capsys):
    tool=runpy.run_path(str(
        ROOT/"scripts/review_predictive_revenue_v421_real_cash_gaps_20261025.py"))
    assert tool["main"]([],repo_root=tmp_path)==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="V421_EXPLICIT_READ_ONLY_REQUIRED"
    assert tool["main"](["--read-only"],repo_root=tmp_path)==0
    result=json.loads(capsys.readouterr().out)
    assert result["independent_proof_categories_not_admitted"]==7
    assert result["eligible_cash_training_examples"]==0
    assert result["production_db_read_or_write_performed"] is False
    assert result["execution_authority"]=="none"


def test_v421_forecast_custody_contains_no_production_execution_or_db_writes():
    source=(ROOT/"empire_os/predictive_revenue_v421_forecast_custody.py").read_text()
    for forbidden in ("psycopg.connect(", "CREATE TABLE ", "INSERT INTO ",
                      "execute_payment(", "model.fit(", "send_email(", "systemctl"):
        assert forbidden not in source
