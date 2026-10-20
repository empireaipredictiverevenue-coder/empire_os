"""Full row-by-row Exchange selection review, never contact/fulfilment approval.

A canonical snapshot is bounded *selection* only: a complete 176-row read is
not an independent individual prospect identity/consent/buyer verification.
Return internal owner-scoped task identifiers, blocker buckets and next-step
receipts, never lead payload, names, contacts, sales claims or provider content.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from collections.abc import Mapping
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from typing import Any

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory

SCHEMA="empire.exchange.inventory_owner_triage.v1"
REASONS={
    ("blocked_missing_evidence","market_identity_missing"):(
        "IDENTITY_MARKET","EXISTING_DATA_CLOUD_OWNER",
        "RECONCILE_MARKET_GEO_AND_CORRIDOR_WITH_ORIGINAL_PROSPECT"),
    ("blocked_missing_evidence","missing_active_identity_link"):(
        "IDENTITY_LINK","EXISTING_CRM_IDENTITY_OWNER",
        "FIND_AUTHENTIC_ACTIVE_CANONICAL_PROSPECT_ENTITY_LINK_AND_TENANT"),
    ("overflow_no_capacity","no_eligible_buyer_capacity"):(
        "BUYER_CAPACITY","EXISTING_SALES_AND_EXCHANGE_OWNER",
        "VERIFY_CURRENT_NAMED_BUYER_ACCEPTING_SCOPE_TERMS_CAPACITY_AND_SUPPRESSION"),
}
MAX_ROWS=1000
MAX_SEATS=3000
MAX_CORRIDOR_LEN=170


def _hold(reason:str)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,"state":"HOLD","reason":reason,
        "source_rows_fully_triaged":False,"records_reviewed":0,
        "owner_tasks":[],"blocker_counts":{},
        "leads_verified_sellable":0,"verified_buyer_capacity":0,
        "authorized_outbound":False,"customer_delivery_authorized":False,
        "crm_writes":False,"revenue_verified_cents":0,
    }


def review_exchange_inventory_for_owner(
    snapshot:Mapping[str,Any],*,now:datetime|None=None,
)->dict[str,Any]:
    if not isinstance(snapshot,Mapping):
        return _hold("canonical_snapshot_unavailable")
    at=now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    projection=build_lead_exchange_live_inventory(snapshot,now=at)
    if projection.get("state")!="FRESH_CANONICAL_SNAPSHOT":
        return _hold("canonical_snapshot_untrusted_or_stale")
    inventory=snapshot.get("inventory")
    seats=snapshot.get("buyer_seats")
    if (not isinstance(inventory,list) or not isinstance(seats,list)
            or len(inventory)>MAX_ROWS or len(seats)>MAX_SEATS
            or len(inventory)!=snapshot.get("inventory_count")
            or len(seats)!=snapshot.get("buyer_seat_count")):
        return _hold("snapshot_selection_bounds_or_counts_invalid")
    result=[]
    ids=set()
    blockers=Counter()
    sectors=Counter()
    corr=Counter()
    for row in inventory:
        if not isinstance(row,Mapping):
            return _hold("non_structured_inventory_row")
        pid=row.get("prospect_id")
        state=row.get("state")
        reason=row.get("reason")
        if not isinstance(pid,str) or not 1<=len(pid)<=128 or pid in ids:
            return _hold("missing_or_duplicate_prospect_identity")
        ids.add(pid)
        route=REASONS.get((state,reason))
        if route is None:
            # New schemas/states must be explicitly reviewed, never silently
            # skipped or promoted to 'eligible lead' by a stale triage engine.
            return _hold("unreviewed_or_promoted_inventory_state")
        bucket,owner,action=route
        market=row.get("metro")
        niche=row.get("niche_family")
        corridor=row.get("corridor_key")
        if bucket=="BUYER_CAPACITY":
            if not all(isinstance(v,str) and 1<=len(v)<=MAX_CORRIDOR_LEN
                       for v in (market,niche,corridor)):
                return _hold("unusable_buyer_capacity_route")
        elif bucket=="IDENTITY_LINK":
            if not all(isinstance(v,str) and 1<=len(v)<=MAX_CORRIDOR_LEN
                       for v in (market,niche,corridor)):
                # With identity-link missing, don't assume market; move to
                # market-identity owner instead of forging route relevance.
                bucket="IDENTITY_MARKET"
                owner="EXISTING_DATA_CLOUD_OWNER"
                action="RECONCILE_MARKET_GEO_AND_CORRIDOR_WITH_ORIGINAL_PROSPECT"
        # Market identity held rows may be missing some or all route fields.
        market = market if isinstance(market,str) and market.strip() else "UNKNOWN_MARKET"
        niche = niche if isinstance(niche,str) and niche.strip() else "UNKNOWN_NICHE"
        corridor = corridor if isinstance(corridor,str) and corridor.strip() else "UNKNOWN_CORRIDOR"
        if any(len(s)>MAX_CORRIDOR_LEN for s in (market,niche,corridor)):
            return _hold("oversize_market_or_route_value")
        task_id=sha256(f"exchange-triage-v1:{pid}:{state}:{reason}".encode()).hexdigest()[:24]
        result.append({
            "task_id":task_id,"canonical_prospect_id_private":pid,
            "observed_state":state,"observed_reason":reason,
            "market":market,"niche":niche,"corridor":corridor,
            "owner_bucket":bucket,"existing_owner":owner,
            "next_action":action,
            "source_evidence_fresh":True,
            "independent_identity_verified":False,
            "buyer_capacity_verified":False,
            "consent_and_transfer_rights_verified":False,
            "commercial_purchase_accepted":False,
            "outbound_authorized":False,
            "crm_writer_authorized":False,
        })
        blockers[bucket]+=1
        sectors[(niche,market)]+=1
        corr[(bucket,niche,market,corridor)]+=1
    # No source prospect is dropped, merged or implicitly released.
    if len(result)!=len(inventory) or sum(blockers.values())!=len(inventory):
        return _hold("source_selection_not_fully_accounted")
    if (projection.get("selected_inventory_records")!=len(result)
            or projection.get("active_capacity_seat_records")!=0
            or projection.get("allocation_candidate_records")!=0
            or projection.get("allocated_records")!=0):
        return _hold("snapshot_contains_unhandled_live_candidate_or_capacity")

    seat_states=Counter()
    for seat in seats:
        if not isinstance(seat,Mapping) or seat.get("seat_state")!="blocked_missing_evidence":
            return _hold("unreviewed_or_active_buyer_seat")
        seat_states["blocked_missing_evidence"]+=1
    return {
        "schema_version":SCHEMA,
        "state":"ALL_SELECTED_RECORDS_TRIAGED_NOT_COMMERCIAL_VERIFIED",
        "source_snapshot_observed_at":snapshot.get("observed_at"),
        "reviewed_at":at.astimezone(timezone.utc).isoformat(),
        "source_rows_fully_triaged":True,
        "source_scope":"BOUNDED_CANONICAL_EXCHANGE_SELECTION_NOT_ALL_DB",
        "records_reviewed":len(result),
        "unique_prospects_checked":len(ids),
        "blocker_counts":dict(sorted(blockers.items())),
        "buyer_seat_records_reviewed":len(seats),
        "buyer_seat_state_counts":dict(seat_states),
        "owner_tasks":sorted(result,key=lambda r:(r["owner_bucket"],r["market"],r["niche"],r["task_id"])),
        "market_group_counts":[
            {"niche":n,"market":m,"count":v}
            for (n,m),v in sectors.most_common()
        ],
        "owner_work_batches":[
            {"bucket":b,"niche":n,"market":m,"corridor":c,"records":v}
            for (b,n,m,c),v in sorted(corr.items(),key=lambda k:(-k[1],k[0]))
        ],
        "a2a_research_is_not_canonical_inventory":True,
        "identity_links_independently_checked":False,
        "canonical_qualified_consumer_enquiries_verified":0,
        "leads_verified_sellable":0,
        "verified_buyer_capacity":0,
        "authorized_outbound":False,
        "customer_delivery_authorized":False,
        "crm_writes":False,
        "revenue_verified_cents":0,
    }


def redacted_founder_summary(review:Mapping[str,Any])->dict[str,Any]:
    if review.get("state")!="ALL_SELECTED_RECORDS_TRIAGED_NOT_COMMERCIAL_VERIFIED":
        return _hold("owner_review_not_complete")
    return {k:v for k,v in review.items() if k not in ("owner_tasks",)}
