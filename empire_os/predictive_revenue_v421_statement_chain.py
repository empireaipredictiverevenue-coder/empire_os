"""V4.21 declared multi-statement continuity vs 30/60/90 cash horizons.

Pure offline, one original signed Smart CRM tenant and the existing V4.21
bilateral and single-statement validators. No public-key issuer authority,
whole-bank statement completeness, independent settlement or model promotion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import json

from empire_os.predictive_revenue_v421_dual_entry import (
    _clock, _check_id, reconcile_v421_bilateral_cash_held,
)
from empire_os.predictive_revenue_v421_statement_closure import (
    review_v421_supplied_bank_statement_held, MANIFEST_FIELDS, POSITION_FIELDS,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v421.statement_chain_held.v1"
ENTRY_FIELDS=frozenset(("manifest","positions"))


def review_v421_statement_chain_held(
    *,research_twin:dict[str,Any],
    signed_crm_bearer:str,crm_verifier:SignedCrmTenantVerifier,
    original_order_snapshots:tuple[dict[str,Any],...],
    buyer_remittance_advices:tuple[dict[str,Any],...],
    external_bank_events:tuple[dict[str,Any],...],
    supplied_statements:tuple[dict[str,Any],...],
    pinned_buyer_keys:dict[str,bytes],pinned_bank_keys:dict[str,bytes],
    as_of:datetime,
)->dict[str,Any]:
    if type(supplied_statements) is not tuple or not 1<=len(supplied_statements)<=16:
        raise ValueError("V421_BOUNDED_STATEMENT_CHAIN_REQUIRED")
    # Signed CRM, original tenant/source/currency, signed buyer/bank events,
    # duplicate event IDs and bank-buyer signing key separation rechecked.
    all_events=reconcile_v421_bilateral_cash_held(
        research_twin=research_twin,signed_crm_bearer=signed_crm_bearer,
        crm_verifier=crm_verifier,original_order_snapshots=original_order_snapshots,
        buyer_remittance_advices=buyer_remittance_advices,
        external_bank_events=external_bank_events,
        pinned_buyer_keys=pinned_buyer_keys,pinned_bank_keys=pinned_bank_keys,
        as_of=as_of,
    )
    manifests=[]
    seen_ids=set()
    for part in supplied_statements:
        if type(part) is not dict or set(part)!=ENTRY_FIELDS:
            raise ValueError("V421_EXACT_STATEMENT_CHAIN_ENTRY_REQUIRED")
        m=part["manifest"]
        if type(m) is not dict or set(m)!=MANIFEST_FIELDS:
            raise ValueError("V421_EXACT_SIGNED_MANIFEST_REQUIRED")
        if type(part["positions"]) is not tuple:
            raise ValueError("V421_EXACT_SEQUENCE_POSITION_TUPLE_REQUIRED")
        sid=_check_id(m["statement_id"])
        if sid in seen_ids:
            raise ValueError("V421_DUPLICATE_STATEMENT_ID")
        seen_ids.add(sid)
        manifests.append((_clock(m["window_start"]),_clock(m["window_end"]),m,part["positions"]))
    # Ordering is not an authority claim; duplicate or overlapping intervals
    # cannot silently double count events or increase maturity coverage.
    ordered=sorted(manifests,key=lambda item:(item[0],item[1]))
    issues=set()
    first=ordered[0][2]
    issuer=first["issuer_id"]
    account=first["account_digest"]
    period_start=ordered[0][0]
    period_end=ordered[-1][1]
    last_close=None
    last_end=None
    last_sequence=None
    receipts=[]
    referenced_event_ids=set()
    for start,end,manifest,positions in ordered:
        if manifest["issuer_id"]!=issuer or manifest["account_digest"]!=account:
            issues.add("ACCOUNT_OR_ISSUER_CHANGED")
        if last_end is not None:
            if start>last_end:issues.add("STATEMENT_DATE_GAP")
            if start<last_end:issues.add("STATEMENT_DATE_OVERLAP")
            if manifest["opening_balance_minor"]!=last_close:
                issues.add("CROSS_STATEMENT_BALANCE_BREAK")
            if manifest["first_sequence"]!=last_sequence+1:
                issues.add("CROSS_STATEMENT_SEQUENCE_BREAK")
        last_end=end
        last_close=manifest["closing_balance_minor"]
        last_sequence=manifest["last_sequence"]
        event_subset=tuple(
            event for event in external_bank_events
            if start<=_clock(event["cleared_at"])<end
        )
        # A signed event in overlapping statement windows cannot be
        # accepted just because each statement otherwise balances.
        for event in event_subset:
            eid=event["event_id"]
            if eid in referenced_event_ids:
                issues.add("REPLAYED_EXTERNAL_EVENT")
            referenced_event_ids.add(eid)
        receipt=review_v421_supplied_bank_statement_held(
            research_twin=research_twin,signed_crm_bearer=signed_crm_bearer,
            crm_verifier=crm_verifier,original_order_snapshots=original_order_snapshots,
            buyer_remittance_advices=buyer_remittance_advices,
            external_bank_events=event_subset,
            statement_manifest=manifest,statement_positions=positions,
            pinned_buyer_keys=pinned_buyer_keys,pinned_bank_keys=pinned_bank_keys,
            as_of=as_of,
        )
        if receipt["internal_supplied_statement_consistent"] is not True:
            issues.add("SINGLE_STATEMENT_NOT_CLOSED")
        receipts.append(receipt)
    unassigned={
        event["event_id"] for event in external_bank_events
        if event["event_id"] not in referenced_event_ids
    }
    if unassigned:
        issues.add("EXTERNAL_EVENTS_WITHOUT_STATEMENT")
    if period_end-period_start>timedelta(days=400):
        raise ValueError("V421_BANK_STATEMENT_CHAIN_SPAN_LIMIT")
    accepted=tuple(_clock(o["accepted_at"]) for o in original_order_snapshots)
    cutoff=as_of.astimezone(timezone.utc)
    horizon_results=[]
    for days in (30,60,90):
        target=max(t+timedelta(days=days) for t in accepted)
        # Half-open intervals: the final date must extend strictly beyond
        # the last cohort maturity point to cover its whole elapsed window.
        cursor=min(accepted)
        calendar_covered=ordered[0][0]<=cursor
        if calendar_covered:
            for start,end,_,_ in ordered:
                if start>cursor:
                    calendar_covered=False
                    break
                cursor=max(cursor,end)
                if cursor>target:
                    break
        calendar_covered=(
            calendar_covered and target<=cutoff and cursor>target
        )
        horizon_results.append({
            "horizon_days":days,
            "all_selected_orders_mature":target<=cutoff,
            "declared_contiguous_statement_calendar_coverage":calendar_covered,
            "cash_outcome_independently_verified":False,
            "cash_finality_or_refund_complete":False,
            "training_ground_truth_eligible":False,
        })
    closed=not issues
    digest=sha256(json.dumps(
        [m for _,_,m,_ in ordered],sort_keys=True,
        separators=(",",":"),allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "mode":"OFFLINE_SIMULATION",
        "status":(
            "V421_DECLARED_STATEMENT_CHAIN_CLOSED_HELD"
            if closed else "V421_DECLARED_STATEMENT_CHAIN_GAPS_HELD"
        ),
        "canonical_tenant_id":all_events["canonical_tenant_id"],
        "currency_code":all_events["currency_code"],
        "declared_account_digest":account,
        "declared_issuer_id":issuer,
        "declared_chain_start_utc":period_start.isoformat(),
        "declared_chain_end_utc":period_end.isoformat(),
        "statement_count":len(ordered),
        "internally_closed_statement_count":sum(
            x["internal_supplied_statement_consistent"] for x in receipts
        ),
        "global_supplied_event_count":len(external_bank_events),
        "events_unassigned_to_statements":len(unassigned),
        "declared_chain_contiguous_and_balanced":closed,
        "issues":sorted(issues),
        "original_orders_selected":all_events["order_rows_selected"],
        "orders_with_discrepancies":all_events["orders_with_discrepancy"],
        "orphan_external_credit_events":all_events["orphan_external_credit_events"],
        "all_supplied_order_claims_reconciled":all_events["all_supplied_claims_reconciled"],
        "horizons":horizon_results,
        "chain_manifest_digest_not_bank_proof":digest,
        "issuer_public_key_independently_attested":False,
        "bank_statement_inventory_complete_verified":False,
        "original_empiredb_order_population_complete_verified":False,
        "source_rights_verified":False,
        "refund_and_chargeback_finality_verified":False,
        "actual_realised_net_cash_minor":None,
        "independent_cash_residuals_for_training":None,
        "verified_30_60_90_cash_forecasts":None,
        "production_model_weights_updated":False,
        "training_samples_eligible":0,
        "economic_memory_written":False,
        "funds_moved":False,
        "outbound_authorized":False,
        "paid_traffic_authorized":False,
        "execution_authority":"none",
    }
