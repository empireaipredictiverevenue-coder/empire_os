"""V4.21 held issuer-statement completeness within ONE supplied statement.

Joins the already original-CRM-bound two-way order ledger, independently
submitted external signed event manifest, declared contiguous transaction
sequences, credit/debit totals and opening/closing balances. Caller-pinned
keys have NO independent bank authority. No SQL, network, training or writes.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import json
from empire_os.predictive_revenue_v421_dual_entry import (
    _clock,_check_id,_digest,_check_signature,_keys,_money,
    CASH_FIELDS,MAX_MINOR,
    reconcile_v421_bilateral_cash_held,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v421.statement_closure_held.v1"
MANIFEST_FIELDS=frozenset((
    "statement_id","issuer_id","account_digest","tenant_id","currency_code",
    "window_start","window_end","issued_at","record_count",
    "first_sequence","last_sequence","credit_event_count","debit_event_count",
    "gross_credit_minor","gross_debit_minor",
    "opening_balance_minor","closing_balance_minor",
    "sequenced_events_sha256","signature_hex",
))
POSITION_FIELDS=frozenset(("statement_id","event_id","sequence_no"))


def _sequence_hash(records:tuple[dict[str,Any],...])->str:
    return sha256(json.dumps(records,sort_keys=True,separators=(",",":"),
                     allow_nan=False).encode()).hexdigest()


def review_v421_supplied_bank_statement_held(
    *,research_twin:dict[str,Any],signed_crm_bearer:str,
    crm_verifier:SignedCrmTenantVerifier,
    original_order_snapshots:tuple[dict[str,Any],...],
    buyer_remittance_advices:tuple[dict[str,Any],...],
    external_bank_events:tuple[dict[str,Any],...],
    statement_manifest:dict[str,Any],
    statement_positions:tuple[dict[str,Any],...],
    pinned_buyer_keys:dict[str,bytes],
    pinned_bank_keys:dict[str,bytes],
    as_of:datetime,
)->dict[str,Any]:
    # Force a fresh original CRM and original source/currency/tenant verification.
    # The underlying bilateral report counts BOTH unmatched ledger and
    # external issuer events. Its numbers never authorize cash-based learning.
    reconciliation=reconcile_v421_bilateral_cash_held(
        research_twin=research_twin,signed_crm_bearer=signed_crm_bearer,
        crm_verifier=crm_verifier,original_order_snapshots=original_order_snapshots,
        buyer_remittance_advices=buyer_remittance_advices,
        external_bank_events=external_bank_events,
        pinned_buyer_keys=pinned_buyer_keys,pinned_bank_keys=pinned_bank_keys,
        as_of=as_of,
    )
    if (type(statement_manifest) is not dict
        or set(statement_manifest)!=MANIFEST_FIELDS
        or type(statement_positions) is not tuple
        or len(statement_positions)>2000):
        raise ValueError("V421_EXACT_SIGNED_STATEMENT_CONTRACT_REQUIRED")
    m=statement_manifest
    account=_digest(m["account_digest"])
    statement_id=_check_id(m["statement_id"])
    if (m["tenant_id"]!=reconciliation["canonical_tenant_id"]
        or m["currency_code"]!=reconciliation["currency_code"]):
        raise ValueError("V421_STATEMENT_TENANT_CURRENCY_MISMATCH")
    issuer=m["issuer_id"]
    keys=_keys(pinned_bank_keys)
    if issuer not in keys:
        raise ValueError("V421_STATEMENT_ISSUER_KEY_UNKNOWN")
    _check_signature(m,keys[issuer])
    start,end,issued=_clock(m["window_start"]),_clock(m["window_end"]),_clock(m["issued_at"])
    cutoff=as_of.astimezone(timezone.utc)
    if not (timedelta(0)<end-start<=timedelta(days=31)
            and end<=issued<=cutoff):
        raise ValueError("V421_STATEMENT_WINDOW_OR_ISSUE_TIME_INVALID")
    fields=(
        "record_count","first_sequence","last_sequence",
        "credit_event_count","debit_event_count",
        "gross_credit_minor","gross_debit_minor",
        "opening_balance_minor","closing_balance_minor",
    )
    if any(type(m[key]) is not int for key in fields):
        raise ValueError("V421_INTEGER_STATEMENT_BOUNDS_REQUIRED")
    if (not 0<=m["record_count"]<=2000
        or not 0<=m["credit_event_count"]<=2000
        or not 0<=m["debit_event_count"]<=2000
        or not 1<=m["first_sequence"]<=10000000
        or not 0<=m["last_sequence"]<=10000000
        or any(abs(m[key])>MAX_MINOR*2000 for key in (
            "gross_credit_minor","gross_debit_minor",
            "opening_balance_minor","closing_balance_minor"
        ))
        or m["gross_credit_minor"]<0 or m["gross_debit_minor"]<0):
        raise ValueError("V421_OUT_OF_BOUNDS_SIGNED_STATEMENT")
    _digest(m["sequenced_events_sha256"])

    reasons=set()
    positions_by_event={}
    sequence_seen=set()
    for pos in statement_positions:
        if type(pos) is not dict or set(pos)!=POSITION_FIELDS:
            raise ValueError("V421_EXACT_SEQUENCE_POSITION_FIELDS_REQUIRED")
        if _check_id(pos["statement_id"])!=statement_id:
            raise ValueError("V421_FOREIGN_STATEMENT_SEQUENCE")
        ident=_check_id(pos["event_id"])
        seq=pos["sequence_no"]
        if type(seq) is not int or not 1<=seq<=10000000:
            raise ValueError("V421_BOUNDED_SEQUENCE_REQUIRED")
        if ident in positions_by_event:
            reasons.add("DUPLICATED_EVENT_POSITION")
        if seq in sequence_seen:
            reasons.add("DUPLICATED_SEQUENCE")
        positions_by_event[ident]=seq
        sequence_seen.add(seq)

    # Verify that supplied event content and signed statement belong to this
    # same claimed institution and exact, explicitly bounded statement window.
    events_by_id={}
    outside_window=0
    wrong_issuer=0
    for event in external_bank_events:
        if type(event) is not dict or set(event)!=CASH_FIELDS:
            raise ValueError("V421_EXACT_BANK_EVENT_FIELDS_REQUIRED")
        ident=_check_id(event["event_id"])
        if ident in events_by_id:
            raise ValueError("V421_DUPLICATE_SIGNED_EVENT_ID")
        events_by_id[ident]=event
        if event["issuer_id"]!=issuer:
            wrong_issuer+=1
        if not start<=_clock(event["cleared_at"])<end:
            outside_window+=1
        if _clock(event["cleared_at"])>issued:
            reasons.add("EVENT_AFTER_STATEMENT_ISSUED")
    if wrong_issuer:
        reasons.add("EVENT_ISSUER_MISMATCH")
    if outside_window:
        reasons.add("EVENT_OUTSIDE_WINDOW")

    missing_positions=set(events_by_id)-set(positions_by_event)
    extra_positions=set(positions_by_event)-set(events_by_id)
    if missing_positions or extra_positions:
        reasons.add("INCOMPLETE_EVENT_SEQUENCE_BINDING")
    if m["record_count"]!=len(statement_positions):
        reasons.add("STATEMENT_ROW_COUNT_MISMATCH")
    if m["record_count"]!=len(events_by_id):
        reasons.add("SIGNED_STATEMENT_EVENT_COUNT_MISMATCH")
    declared_span=m["last_sequence"]-m["first_sequence"]+1
    if declared_span!=m["record_count"] or not 0<=declared_span<=2000:
        reasons.add("DECLARED_SEQUENCE_RANGE_MISMATCH")
    if (declared_span<0 or declared_span>2000
        or sequence_seen!=set(range(m["first_sequence"],m["last_sequence"]+1))):
        reasons.add("MISSING_OR_OUT_OF_RANGE_SEQUENCE")

    ordered=tuple(
        {"sequence_no":pos["sequence_no"],"event":events_by_id[pos["event_id"]]}
        for pos in sorted(
            (p for p in statement_positions if p["event_id"] in events_by_id),
            key=lambda p:p["sequence_no"],
        )
    )
    observed_digest=_sequence_hash(ordered)
    if observed_digest!=m["sequenced_events_sha256"]:
        reasons.add("EVENT_CONTENT_DIGEST_MISMATCH")
    credit_events=[e for e in external_bank_events if e["direction"]=="CREDIT"]
    debit_events=[e for e in external_bank_events if e["direction"]=="DEBIT"]
    credits=sum(e["amount_minor"] for e in credit_events)
    debits=sum(e["amount_minor"] for e in debit_events)
    if (len(credit_events)!=m["credit_event_count"]
        or len(debit_events)!=m["debit_event_count"]
        or len(credit_events)+len(debit_events)!=m["record_count"]):
        reasons.add("CREDIT_DEBIT_EVENT_COUNTS_MISMATCH")
    if credits!=m["gross_credit_minor"] or debits!=m["gross_debit_minor"]:
        reasons.add("CREDIT_DEBIT_TOTALS_MISMATCH")
    if m["opening_balance_minor"]+credits-debits!=m["closing_balance_minor"]:
        reasons.add("OPENING_CLOSING_BALANCE_MISMATCH")

    # Coverage of time on a *supplied* statement is not proof of
    # complete bank account evidence. Later refunds can occur outside it.
    accepted_times=tuple(_clock(o["accepted_at"]) for o in original_order_snapshots)
    declared_horizon_windows=[
        {
            "horizon_days":days,
            "one_supplied_statement_spans_order_horizon":(
                start<=min(accepted_times)
                and end>max(t+timedelta(days=days) for t in accepted_times)
            ),
            "bank_cash_ground_truth_eligible":False,
            "refund_finality_independently_verified":False,
        }
        for days in (30,60,90)
    ]
    closed=not reasons
    return {
        "schema_version":SCHEMA,
        "status":(
            "V421_SUPPLIED_STATEMENT_INTERNALLY_CLOSED_HELD"
            if closed else "V421_SUPPLIED_STATEMENT_GAPS_HELD"
        ),
        "mode":"OFFLINE_SIMULATION",
        "canonical_tenant_id":reconciliation["canonical_tenant_id"],
        "currency_code":reconciliation["currency_code"],
        "statement_id":statement_id,
        "account_digest":account,
        "issuer_id":issuer,
        "window_start_utc":start.isoformat(),
        "window_end_utc":end.isoformat(),
        "declared_record_count":m["record_count"],
        "supplied_event_count":len(events_by_id),
        "sequence_binding_missing_count":len(missing_positions),
        "sequence_binding_extra_count":len(extra_positions),
        "event_outside_window_count":outside_window,
        "wrong_issuer_event_count":wrong_issuer,
        "gross_credit_minor_in_supplied_events":credits,
        "gross_debit_minor_in_supplied_events":debits,
        "signed_statement_balance_math_consistent":(
            "OPENING_CLOSING_BALANCE_MISMATCH" not in reasons
        ),
        "internal_supplied_statement_consistent":closed,
        "reconciliation_matched_order_claims":reconciliation["matched_order_claims"],
        "reconciliation_discrepant_orders":reconciliation["orders_with_discrepancy"],
        "reconciliation_orphan_external_credit_events":(
            reconciliation["orphan_external_credit_events"]
        ),
        "issues":sorted(reasons),
        "declared_30_60_90_window_coverage":declared_horizon_windows,
        "manifest_digest_not_independent_bank_proof":sha256(
            json.dumps(m,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        ).hexdigest(),
        "cryptographic_signature_valid_for_caller_pinned_bank_key":True,
        "issuer_public_key_proven_independently":False,
        "account_ownership_verified":False,
        "complete_bank_account_window_population_verified":False,
        "all_bank_statement_windows_provided_verified":False,
        "original_empiredb_order_snapshot_independently_verified":False,
        "refund_and_chargeback_finality_verified":False,
        "source_licensing_independently_verified":False,
        "accepted_order_cash_baseline_verified_minor":None,
        "verified_30_60_90_cash_forecasts":None,
        "residual_ground_truth_admitted":False,
        "training_samples_eligible":0,
        "model_weights_updated":False,
        "economic_memory_written":False,
        "outbound_authorized":False,
        "paid_traffic_authorized":False,
        "funds_moved":False,
        "execution_authority":"none",
    }
