#!/usr/bin/env python3
"""Revenue gap evidence: bounded aggregate counts, no source rows or writes.

Only examine the previously authenticated founder tenant. This is a
diagnostic of the *existing* commercial ledger, not a revenue recognizer,
payer verifier, payment network integration or a grant to the reader login.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

from scripts.provision_revenue_event_evidence_login_20261018 import TENANT,pg
from scripts.review_rev052_committed_login_readonly_20261018 import CATALOG_SQL

LIMIT = 5001
SCHEMA = "empire.rev054.existing_commercial_lifecycle_gaps.v1"
STAGES = (
    "tenant_events_sampled",
    "recognized",
    "flagged_actual",
    "linked_order",
    "same_buyer",
    "same_tenant",
    "product_match",
    "price_match",
    "settled_order",
    "lineage_match",
    "eligible_nonfuture",
)

# Event sample is the 5001 latest events owned by the founder tenant. The
# bounded sample is expressly NOT a complete revenue census. Output is only
# aggregate counts and safe category names, never UUIDs, names, amounts, PII,
# source rows or payloads. All stages are cumulative and monotone.
STAGE_SQL = f"""BEGIN READ ONLY;
SET LOCAL statement_timeout='7000ms';
SET LOCAL lock_timeout='1500ms';
WITH
buyers AS MATERIALIZED (
  SELECT b.id FROM public.buyers b
   WHERE b.org_id='{TENANT}'::uuid
   ORDER BY b.id LIMIT {LIMIT}
),
orders AS MATERIALIZED (
  SELECT o.id,o.buyer_id,o.product_id,o.price_cents,o.state,
         o.settled_at,o.commercial_payload
    FROM public.fulfilment_orders o
    JOIN buyers b ON b.id=o.buyer_id
   ORDER BY o.id DESC LIMIT {LIMIT}
),
events AS MATERIALIZED (
  SELECT e.id,e.event_type,e.payload,e.fulfilment_order_id,
         e.buyer_id,e.product_id,e.amount_cents,e.occurred_at
    FROM public.commercial_events e
    JOIN buyers b ON b.id=e.buyer_id
   ORDER BY e.occurred_at DESC,e.id DESC LIMIT {LIMIT}
),
joined AS (
 SELECT e.id,
        (e.event_type='revenue_recognized') AS g_recognized,
        (e.payload->>'actual_revenue'='true') AS g_flagged,
        (o.id IS NOT NULL) AS g_link,
        (e.buyer_id=o.buyer_id) AS g_same_buyer,
        (ob.org_id='{TENANT}'::uuid) AS g_same_tenant,
        (e.product_id IS NOT NULL AND e.product_id=o.product_id) AS g_product,
        (e.amount_cents>0 AND o.price_cents>0
            AND e.amount_cents=o.price_cents) AS g_price,
        (o.state IN ('settled','outcome_captured')
            AND o.settled_at IS NOT NULL) AS g_settled,
        (e.payload->'causal_lineage' IS NOT NULL
            AND e.payload->'causal_lineage'<>'{{}}'::jsonb
            AND e.payload->'causal_lineage'
                IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage') AS g_lineage,
        (e.occurred_at<=clock_timestamp()) AS g_nonfuture
 FROM events e
 LEFT JOIN public.fulfilment_orders o ON o.id=e.fulfilment_order_id
 LEFT JOIN public.buyers ob ON ob.id=o.buyer_id
),
scored AS (
 SELECT id,
   (g_recognized IS TRUE) AS s1,
   ((g_recognized AND g_flagged) IS TRUE) AS s2,
   ((g_recognized AND g_flagged AND g_link) IS TRUE) AS s3,
   ((g_recognized AND g_flagged AND g_link
       AND g_same_buyer) IS TRUE) AS s4,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant) IS TRUE) AS s5,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant AND g_product) IS TRUE) AS s6,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant AND g_product AND g_price) IS TRUE) AS s7,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant AND g_product AND g_price AND g_settled) IS TRUE) AS s8,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant AND g_product AND g_price AND g_settled
       AND g_lineage) IS TRUE) AS s9,
   ((g_recognized AND g_flagged AND g_link AND g_same_buyer
       AND g_same_tenant AND g_product AND g_price AND g_settled
       AND g_lineage AND g_nonfuture) IS TRUE) AS s10
 FROM joined
)
SELECT pg_catalog.jsonb_build_object(
 'founder_buyers_sampled',(SELECT count(*) FROM buyers),
 'founder_orders_sampled',(SELECT count(*) FROM orders),
 'tenant_events_sampled',(SELECT count(*) FROM events),
 'recognized',(SELECT count(*) FROM scored WHERE s1),
 'flagged_actual',(SELECT count(*) FROM scored WHERE s2),
 'linked_order',(SELECT count(*) FROM scored WHERE s3),
 'same_buyer',(SELECT count(*) FROM scored WHERE s4),
 'same_tenant',(SELECT count(*) FROM scored WHERE s5),
 'product_match',(SELECT count(*) FROM scored WHERE s6),
 'price_match',(SELECT count(*) FROM scored WHERE s7),
 'settled_order',(SELECT count(*) FROM scored WHERE s8),
 'lineage_match',(SELECT count(*) FROM scored WHERE s9),
 'eligible_nonfuture',(SELECT count(*) FROM scored WHERE s10)
)::text;
ROLLBACK;"""


def evaluate_counts(values: dict[str,Any]) -> dict[str,Any]:
    all_keys=("founder_buyers_sampled","founder_orders_sampled")+STAGES
    if (not isinstance(values,dict)
        or set(values)!=set(all_keys)
        or any(type(values[k]) is not int or values[k]<0 or values[k]>LIMIT
               for k in all_keys)):
        raise ValueError("INVALID_BOUNDED_AGGREGATE_SHAPE")
    previous=values[STAGES[0]]
    for name in STAGES[1:]:
        if values[name]>previous:
            raise ValueError("NONMONOTONE_STAGE_COUNTS")
        previous=values[name]
    safe={k:values[k] for k in all_keys}
    sampled_truncated=any(values[k]>=LIMIT for k in (
        "founder_buyers_sampled","founder_orders_sampled","tenant_events_sampled"
    ))
    if values["tenant_events_sampled"]==0:
        gap="NO_TENANT_EVENTS_IN_BOUNDED_SCOPE"
    else:
        gap="ALL_RECOGNITION_GATES_HAVE_A_SAMPLE_MATCH"
        for i in range(1,len(STAGES)):
            if values[STAGES[i]]==0:
                gap="FIRST_ZERO_AT_"+STAGES[i].upper()
                break
    return {
        "schema_version":SCHEMA,
        "status":("REV054_SAMPLE_TRUNCATED_REQUIRES_WIDER_REVIEW" if sampled_truncated
                  else "REV054_BOUNDED_LIFECYCLE_GAP_REVIEW_COMPLETE"),
        "mode":"OBSERVE","read_only":True,"database_mutation":False,
        "outbound_sent":False,"payment_changed":False,
        "customer_records_exported":False,
        "payer_or_settlement_externally_verified":False,
        "realised_revenue_verified":False,
        "complete_daily_revenue_census_verified":False,
        "candidate_uuid_disclosed":False,
        "max_records_per_source":LIMIT,
        "sample_truncated_or_limit_reached":sampled_truncated,
        "counts_are_aggregate_only":True,
        "first_zero_gate":gap,
        "counts":safe,
    }


def review(*, admin_query:Callable[[str],str]=pg)->dict[str,Any]:
    report={
        "schema_version":SCHEMA,
        "status":"HOLD_REV054_SOURCE_EVIDENCE_UNAVAILABLE",
        "mode":"OBSERVE","read_only":True,"database_mutation":False,
        "realised_revenue_verified":False,
    }
    try:
        authority=json.loads(admin_query(CATALOG_SQL))
        if (type(authority) is not dict or len(authority)!=16 or
            any(v is not True for v in authority.values())):
            report["stage"]="REV052_AUTHORITY_CATALOG_HOLD"
            return report
    except Exception:
        report["stage"]="REV052_CATALOG_QUERY_UNAVAILABLE"
        return report
    try:
        evidence=json.loads(admin_query(STAGE_SQL))
        return evaluate_counts(evidence)
    except ValueError:
        report["stage"]="UNTRUSTED_AGGREGATE_SHAPE"
    except Exception:
        report["stage"]="LIFECYCLE_AGGREGATE_QUERY_UNAVAILABLE"
    return report


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only-lifecycle-gaps",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only_lifecycle_gaps:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_LIFECYCLE_FLAG_REQUIRED"}))
        return 2
    if os.geteuid()!=0:
        print(json.dumps({"status":"HOLD_ROOT_LOCAL_REQUIRED"}))
        return 2
    result=review()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"].startswith("REV054_") else 2


if __name__=="__main__":
    raise SystemExit(main())
