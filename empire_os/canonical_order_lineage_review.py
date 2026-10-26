"""Original EmpireDB exact opportunity/prospect/entity order lineage, READ ONLY.

An exact FK-backed fulfilment order is a stronger identity continuity receipt
than a market-level GTM hypothesis. This does NOT prove an accepted buyer,
delivered traffic, payment, refund finality or realised revenue. Missing
orders stay missing; callers may not create an order to make a test pass.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import (
    ProspectHandoffHold, review_existing_prospect_entity_tenant,
)

SCHEMA = "empire.canonical.existing_order_opportunity_lineage.v1"
VALID_ORDER_STATES = frozenset({
    "raw","qualified","matched","offered","accepted","delivered",
    "confirmed","invoiced","paid","settled","outcome_captured",
    "rejected","cancelled",
})

def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ProspectHandoffHold("INVALID_" + label)
    try:
        canonical=str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProspectHandoffHold("INVALID_" + label) from exc
    if value != canonical:
        raise ProspectHandoffHold("NON_CANONICAL_" + label)
    return canonical

def review_existing_order_opportunity_lineage(
    cursor: Any, *,
    order_id: str,
    opportunity_id: str,
    prospect_id: str,
    entity_id: str,
    authenticated_tenant_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Verify the SAME exact existing opportunity/order/prospect/entity/tenant.

    The caller must provide a dedicated original signed-CRM restricted reader
    in a READ ONLY transaction. This pure query function cannot independently
    attest cursor provenance. Test connector output is explicitly untrusted.
    """
    order=_uuid(order_id,"ORDER_ID")
    opportunity=_uuid(opportunity_id,"OPPORTUNITY_ID")
    prospect=_uuid(prospect_id,"PROSPECT_ID")
    entity=_uuid(entity_id,"ENTITY_ID")
    tenant=_uuid(authenticated_tenant_id,"AUTHENTICATED_TENANT_ID")
    # First require exact prospect->entity->tenant provenance. A receipt
    # for a different tenant/company cannot be borrowed by an order.
    source=review_existing_prospect_entity_tenant(
        cursor, prospect_id=prospect, entity_id=entity,
        authenticated_tenant_id=tenant, as_of=as_of,
    )
    cursor.execute(
        """
        SELECT id, status
        FROM public.gtm_opportunities
        WHERE id=%s::uuid
        LIMIT 2
        """, (opportunity,),
    )
    gtm=cursor.fetchall()
    if (not isinstance(gtm,list) or len(gtm)!=1
            or not isinstance(gtm[0],(list,tuple)) or len(gtm[0])!=2
            or str(gtm[0][0]) != opportunity):
        raise ProspectHandoffHold("EXACT_EXISTING_GTM_OPPORTUNITY_REQUIRED")
    cursor.execute(
        """
        SELECT id, opportunity_id, prospect_id, entity_id, buyer_id, state
        FROM public.fulfilment_orders
        WHERE id=%s::uuid
        LIMIT 2
        """, (order,),
    )
    rows=cursor.fetchall()
    if (not isinstance(rows,list) or len(rows)!=1
            or not isinstance(rows[0],(tuple,list)) or len(rows[0])!=6):
        raise ProspectHandoffHold("EXACT_EXISTING_FULFILMENT_ORDER_REQUIRED")
    oid, opp, pros, ent, buyer, state=rows[0]
    if (str(oid)!=order or str(opp)!=opportunity
            or str(pros)!=prospect or str(ent)!=entity
            or type(state) is not str or state not in VALID_ORDER_STATES):
        raise ProspectHandoffHold("CANONICAL_ORDER_LINEAGE_MISMATCH")
    # Never allow 'settled' text or payment flag to grant financial authority.
    # The financial and delivery evidence readers remain distinct.
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"EXACT_EXISTING_ORDER_SOURCE_LINEAGE_OBSERVED_REVIEW_ONLY",
        "prospect_id":prospect,
        "entity_id":entity,
        "tenant_id":tenant,
        "opportunity_id":opportunity,
        "fulfilment_order_id":order,
        "source_prospect_entity_ref":source["prospect_entity_source_ref"],
        "original_tenant_binding_ref":source["tenant_entity_binding_ref"],
        "original_gtm_status_reported":str(gtm[0][1]),
        "original_order_state_reported":state,
        "buyer_id_present_on_order":buyer is not None,
        "source_and_order_record_identity_consistent":True,
        "original_crm_reader_login_attested_by_this_function":False,
        "original_buyer_acceptance_verified":False,
        "buyer_capacity_verified":False,
        "fulfilment_verified":False,
        "payment_receipt_verified":False,
        "settlement_finality_verified":False,
        "realised_revenue_verified":False,
        "economic_memory_authorized":False,
        "outbound_authorized":False,
        "database_writes":False,
        "execution_authority":"NONE",
    }


def review_existing_commercial_event_lineage(
    cursor: Any, *,
    event_id: str,
    opportunity_id: str,
    prospect_id: str,
    entity_id: str,
    authenticated_tenant_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Prove an existing immutable event refers to the same source and GTM ID.

    Unlike a fulfilment order this can exist before any order is accepted.
    A self-reported event never becomes an accepted commercial agreement,
    buyer capacity, a right to contact, a payment or profit.
    """
    event=_uuid(event_id,"EVENT_ID")
    opportunity=_uuid(opportunity_id,"OPPORTUNITY_ID")
    prospect=_uuid(prospect_id,"PROSPECT_ID")
    entity=_uuid(entity_id,"ENTITY_ID")
    tenant=_uuid(authenticated_tenant_id,"AUTHENTICATED_TENANT_ID")
    source=review_existing_prospect_entity_tenant(
        cursor, prospect_id=prospect, entity_id=entity,
        authenticated_tenant_id=tenant, as_of=as_of,
    )
    cursor.execute(
        """
        SELECT id, status FROM public.gtm_opportunities
        WHERE id=%s::uuid LIMIT 2
        """, (opportunity,),
    )
    gtm=cursor.fetchall()
    if (not isinstance(gtm,list) or len(gtm)!=1
            or not isinstance(gtm[0],(list,tuple))
            or len(gtm[0])!=2 or str(gtm[0][0])!=opportunity):
        raise ProspectHandoffHold("EXACT_EXISTING_GTM_OPPORTUNITY_REQUIRED")
    cursor.execute(
        """
        SELECT id, event_type, opportunity_id, prospect_id,
               entity_id, fulfilment_order_id
        FROM public.commercial_events
        WHERE id=%s::uuid
        LIMIT 2
        """, (event,),
    )
    rows=cursor.fetchall()
    if (not isinstance(rows,list) or len(rows)!=1
            or not isinstance(rows[0],(list,tuple)) or len(rows[0])!=6):
        raise ProspectHandoffHold("EXACT_EXISTING_COMMERCIAL_EVENT_REQUIRED")
    rid,kind,opp,pros,ent,related_order=rows[0]
    if (str(rid)!=event or not isinstance(kind,str)
            or not 1<=len(kind)<=80 or not kind.strip()
            or str(opp)!=opportunity or str(pros)!=prospect
            or str(ent)!=entity):
        raise ProspectHandoffHold("COMMERCIAL_EVENT_CANONICAL_LINEAGE_MISMATCH")
    return {
        "schema_version":"empire.canonical.existing_commercial_event_lineage.v1",
        "mode":"OBSERVE",
        "status":"EXISTING_EVENT_LINEAGE_OBSERVED_NO_ORDER_AUTHORITY",
        "event_id":event,
        "event_type_reported":kind,
        "opportunity_id":opportunity,
        "prospect_id":prospect,
        "entity_id":entity,
        "tenant_id":tenant,
        "prospect_entity_source_ref":source["prospect_entity_source_ref"],
        "tenant_entity_binding_ref":source["tenant_entity_binding_ref"],
        "gtm_status_reported":str(gtm[0][1]),
        "event_mentions_order":related_order is not None,
        "source_and_event_record_identity_consistent":True,
        "original_crm_reader_login_attested_by_this_function":False,
        "existing_order_verified":False,
        "commercial_terms_approved":False,
        "buyer_acceptance_verified":False,
        "fulfilment_verified":False,
        "payment_receipt_verified":False,
        "revenue_verified":False,
        "outbound_authorized":False,
        "database_writes":False,
        "execution_authority":"NONE",
    }
