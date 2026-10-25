"""V4.21 held pre-outcome forecast custody and proof admission report.

Checks sealed forecast and detached timestamp-witness *claims* before the
opportunity. Caller-pinned Ed25519 keys are not externally authenticated
timestamp authorities. Does NOT admit finance cash / train / change models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v421_dual_entry import (
    _clock, _check_signature, _canonical_signature_message, MAX_MINOR, HEX,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v421.forecast_freeze_custody_held.v1"
FREEZE_FIELDS = frozenset((
    "tenant_id", "source_evidence_digest", "currency_code",
    "cohort_id", "horizon_days", "forecast_net_minor", "locked_at",
    "signature_hex",
))
WITNESS_FIELDS = frozenset((
    "tenant_id", "cohort_id", "horizon_days", "forecast_sha256",
    "witnessed_at", "sequence_no", "signature_hex",
))
HORIZONS = (30,60,90)


def review_v421_forecast_freeze_held(
    *, research_twin:dict[str,Any],signed_crm_bearer:str,
    crm_verifier:SignedCrmTenantVerifier,
    cohort_id:str, earliest_opportunity_at:datetime,
    frozen_forecasts:tuple[dict[str,Any],...],
    timestamp_witnesses:tuple[dict[str,Any],...],
    pinned_forecast_signer:bytes,pinned_witness_signer:bytes,
    as_of:datetime,
)->dict[str,Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V421_ORIGINAL_SIMULATION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V421_ORIGINAL_CRM_MEMBERSHIP_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V421_CRM_BEARER_REQUIRED")
    try:tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:raise ValueError("V421_ACTIVE_SIGNED_CRM_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V421_TENANT_MISMATCH")
    if type(cohort_id) is not str or not 4<=len(cohort_id)<=100 or (
        not cohort_id.isascii() or any(ch.isspace() for ch in cohort_id)
    ):
        raise ValueError("V421_BOUNDED_COHORT_ID_REQUIRED")
    if (type(earliest_opportunity_at) is not datetime
        or earliest_opportunity_at.utcoffset() is None
        or type(as_of) is not datetime or as_of.utcoffset() is None):
        raise ValueError("V421_AWARE_COHORT_CLOCK_REQUIRED")
    inception=earliest_opportunity_at.astimezone(timezone.utc)
    cutoff=as_of.astimezone(timezone.utc)
    if not inception<cutoff<=datetime.now(timezone.utc):
        raise ValueError("V421_PAST_OR_FUTURE_TIME_CUTOFF_DENIED")
    if (type(pinned_forecast_signer) is not bytes or len(pinned_forecast_signer)!=32
        or type(pinned_witness_signer) is not bytes or len(pinned_witness_signer)!=32
        or pinned_forecast_signer==pinned_witness_signer):
        raise ValueError("V421_SEPARATE_ED25519_SIGNING_KEYS_REQUIRED")
    if (type(frozen_forecasts) is not tuple or len(frozen_forecasts)!=3
        or type(timestamp_witnesses) is not tuple or len(timestamp_witnesses)!=3):
        raise ValueError("V421_EXACT_THREE_FORECAST_WITNESS_RECEIPTS_REQUIRED")
    forecasts={}
    for forecast in frozen_forecasts:
        if type(forecast) is not dict or set(forecast)!=FREEZE_FIELDS:
            raise ValueError("V421_EXACT_FORECAST_RECEIPT_FIELDS_REQUIRED")
        if (forecast["tenant_id"]!=tenant
            or forecast["source_evidence_digest"]!=research_twin["source_evidence_digest"]
            or forecast["currency_code"]!=research_twin["currency_code"]
            or forecast["cohort_id"]!=cohort_id):
            raise ValueError("V421_FORECAST_TENANT_SOURCE_CURRENCY_MISMATCH")
        horizon=forecast["horizon_days"]
        if type(horizon) is not int or horizon not in HORIZONS or horizon in forecasts:
            raise ValueError("V421_DUPLICATE_OR_UNKNOWN_FORECAST_HORIZON")
        value=forecast["forecast_net_minor"]
        if type(value) is not int or not -MAX_MINOR<=value<=MAX_MINOR:
            raise ValueError("V421_SIGNED_INTEGER_MINOR_FORECAST_REQUIRED")
        locked=_clock(forecast["locked_at"])
        if not locked<inception:
            raise ValueError("V421_FORECAST_LOCKED_AFTER_OPPORTUNITY_DENIED")
        _check_signature(forecast,pinned_forecast_signer)
        forecasts[horizon]=(forecast,locked)
    witnesses={}
    for witness in timestamp_witnesses:
        if type(witness) is not dict or set(witness)!=WITNESS_FIELDS:
            raise ValueError("V421_EXACT_DETACHED_WITNESS_FIELDS_REQUIRED")
        horizon=witness["horizon_days"]
        if (witness["tenant_id"]!=tenant or witness["cohort_id"]!=cohort_id
            or type(horizon) is not int or horizon not in HORIZONS
            or horizon in witnesses):
            raise ValueError("V421_FOREIGN_OR_DUPLICATE_WITNESS")
        if (type(witness["sequence_no"]) is not int
            or not 1<=witness["sequence_no"]<=10**12):
            raise ValueError("V421_INTEGER_WITNESS_SEQUENCE_REQUIRED")
        digest=witness["forecast_sha256"]
        if type(digest) is not str or HEX.fullmatch(digest) is None:
            raise ValueError("V421_FORECAST_DIGEST_REQUIRED")
        observed=_clock(witness["witnessed_at"])
        _check_signature(witness,pinned_witness_signer)
        witnesses[horizon]=(witness,observed)

    if set(forecasts)!=set(HORIZONS) or set(witnesses)!=set(HORIZONS):
        raise ValueError("V421_COMPLETE_30_60_90_REQUIRED")
    previous_sequence=0
    lines=[]
    for horizon in HORIZONS:
        forecast,locked=forecasts[horizon]
        witness,witness_time=witnesses[horizon]
        expected_digest=sha256(json.dumps(
            forecast,sort_keys=True,separators=(",",":"),allow_nan=False,
        ).encode()).hexdigest()
        if witness["forecast_sha256"]!=expected_digest:
            raise ValueError("V421_WITNESS_FORECAST_CONTENT_MISMATCH")
        if not locked<=witness_time<inception:
            raise ValueError("V421_WITNESS_NOT_OBSERVED_PRE_OUTCOME")
        if witness["sequence_no"]<=previous_sequence:
            raise ValueError("V421_WITNESS_SEQUENCE_REPLAY_OR_ROLLBACK")
        previous_sequence=witness["sequence_no"]
        lines.append({
            "horizon_days":horizon,
            "forecast_net_minor":forecast["forecast_net_minor"],
            "claimed_forecast_locked_at_utc":locked.isoformat(),
            "claimed_witnessed_at_utc":witness_time.isoformat(),
            "content_digest":expected_digest,
            "locally_verified_dual_signatures":True,
            "independent_pre_outcome_timestamp_attested":False,
            "production_training_eligible":False,
        })
    return {
        "schema_version":SCHEMA,
        "status":"V421_PRE_OUTCOME_SIGNED_CUSTODY_CLAIMS_ONLY_HELD",
        "mode":"OFFLINE_SIMULATION",
        "canonical_tenant_id":tenant,
        "cohort_id":cohort_id,
        "currency_code":research_twin["currency_code"],
        "first_opportunity_at_utc":inception.isoformat(),
        "horizons":lines,
        "signed_forecast_content_consistent":True,
        "dual_caller_pinned_signers_differ":True,
        "independent_timestamp_authority_verified":False,
        "pre_outcome_forecast_lock_independently_proven":False,
        "historical_forecast_admitted_to_training":False,
        "bank_settlement_finality_verified":False,
        "realised_cash_ground_truth_minor":None,
        "live_30_60_90_predictions":None,
        "production_model_weights_updated":False,
        "economic_memory_written":False,
        "execution_authority":"none",
    }


def review_v421_calibration_admission_held(
    *, freeze_receipt:dict[str,Any],
    chain_receipt:dict[str,Any],
    finance_readiness:dict[str,Any],
)->dict[str,Any]:
    """Produce a reasoned horizon gate; never infer unprovided bank authority."""
    if (type(freeze_receipt) is not dict
        or freeze_receipt.get("schema_version")!=SCHEMA
        or freeze_receipt.get("status")!="V421_PRE_OUTCOME_SIGNED_CUSTODY_CLAIMS_ONLY_HELD"
        or freeze_receipt.get("pre_outcome_forecast_lock_independently_proven") is not False
        or freeze_receipt.get("execution_authority")!="none"
        or freeze_receipt.get("production_model_weights_updated") is not False
        or freeze_receipt.get("realised_cash_ground_truth_minor") is not None
        or freeze_receipt.get("historical_forecast_admitted_to_training") is not False
        or type(chain_receipt) is not dict
        or chain_receipt.get("schema_version")!="empire.predictive_revenue.v421.statement_chain_held.v1"
        or chain_receipt.get("mode")!="OFFLINE_SIMULATION"
        or chain_receipt.get("actual_realised_net_cash_minor") is not None
        or chain_receipt.get("training_samples_eligible")!=0
        or chain_receipt.get("production_model_weights_updated") is not False
        or chain_receipt.get("issuer_public_key_independently_attested") is not False
        or chain_receipt.get("bank_statement_inventory_complete_verified") is not False
        or chain_receipt.get("refund_and_chargeback_finality_verified") is not False
        or chain_receipt.get("execution_authority")!="none"
        or type(finance_readiness) is not dict
        or finance_readiness.get("schema_version")!="empire.enterprise_finance_source_readiness.v1"
        or finance_readiness.get("execution_authority")!="none"
        or finance_readiness.get("actual_recognised_revenue_independently_verified") is not False):
        raise ValueError("V421_ORIGINAL_HELD_EVIDENCE_RECEIPTS_REQUIRED")
    if (chain_receipt.get("canonical_tenant_id")!=freeze_receipt["canonical_tenant_id"]
        or chain_receipt.get("currency_code")!=freeze_receipt["currency_code"]):
        raise ValueError("V421_EVIDENCE_TENANT_CURRENCY_MISMATCH")
    f=freeze_receipt.get("horizons")
    c=chain_receipt.get("horizons")
    if (type(f) is not list or len(f)!=3 or type(c) is not list
        or len(c)!=3 or [x.get("horizon_days") for x in f]!=list(HORIZONS)
        or [x.get("horizon_days") for x in c]!=list(HORIZONS)):
        raise ValueError("V421_EXACT_30_60_90_HORIZONS_REQUIRED")
    if (finance_readiness.get("required_proofs_not_admitted_count")!=7
        or type(finance_readiness.get("independent_finance_evidence_requirements")) is not list
        or len(finance_readiness["independent_finance_evidence_requirements"])!=7):
        raise ValueError("V421_FINANCE_REVIEW_CANNOT_ASSERT_INDEPENDENT_PROOFS")
    gates=[]
    for frozen,chain in zip(f,c):
        if (chain.get("training_ground_truth_eligible") is not False
            or chain.get("cash_outcome_independently_verified") is not False
            or frozen.get("independent_pre_outcome_timestamp_attested") is not False):
            raise ValueError("V421_FORGED_FINANCIAL_OR_TEMPORAL_AUTHORITY")
        gaps=["INDEPENDENT_BANK_ISSUER_AND_ACCOUNT_NOT_ATTESTED",
              "COMPLETE_BANK_CENSUS_NOT_ATTESTED",
              "REFUND_CLAWBACK_FINALITY_NOT_ATTESTED",
              "PRE_OUTCOME_FORECAST_TIMESTAMP_AUTHORITY_NOT_ATTESTED",
              "SOURCE_RIGHTS_AND_OPPORTUNITY_DENOMINATOR_NOT_ATTESTED"]
        if chain.get("all_selected_orders_mature") is not True:
            gaps.append("COHORT_NOT_MATURE")
        if chain.get("declared_contiguous_statement_calendar_coverage") is not True:
            gaps.append("MISSING_DECLARED_STATEMENT_WINDOW")
        if chain_receipt.get("declared_chain_contiguous_and_balanced") is not True:
            gaps.append("BANK_CLAIM_STATEMENT_CHAIN_BROKEN")
        if (chain_receipt.get("orders_with_discrepancies")!=0
            or chain_receipt.get("orphan_external_credit_events")!=0
            or chain_receipt.get("all_supplied_order_claims_reconciled") is not True):
            gaps.append("UNRESOLVED_ORDER_OR_EXTERNAL_RECEIPT_MISMATCH")
        gates.append({
            "horizon_days":frozen["horizon_days"],
            "unresolved_gate_codes":gaps,
            "independently_verified_cash_actual_minor":None,
            "eligible_for_forecast_retraining":False,
            "calibration_residual_admitted":False,
        })
    return {
        "schema_version":"empire.predictive_revenue.v421.calibration_admission_held.v1",
        "status":"V421_INDEPENDENT_CASH_CALIBRATION_EVIDENCE_NOT_ADMITTED",
        "mode":"OBSERVE",
        "canonical_tenant_id":freeze_receipt["canonical_tenant_id"],
        "horizons":gates,
        "independent_proof_categories_missing":7,
        "source_finance_readiness_status":finance_readiness.get("status"),
        "eligible_training_cohorts":0,
        "verified_cvr_ecac_authorized":False,
        "production_forecast_calibration_authorized":False,
        "model_weights_updated":False,
        "money_moved":False,
        "execution_authority":"none",
    }
