"""Restricted, privacy-preserving Market GPS SQL reader.

Selects market-level counts under the existing materializer role; no raw
contacts, message bodies, payments, buyer authority or fabricated sales.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

# All columns are explicitly allowlisted for restricted role read access.
# DISTINCT prevents multiplying qualifying prospects through multiple linked
# entities, outbound intents or inbound reply records.
RESTRICTED_MARKET_QUERY = """
WITH recent_prospects AS (
    SELECT p.id, lower(btrim(p.niche)) AS niche,
           lower(btrim(p.metro)) AS metro
    FROM public.prospects AS p
    WHERE p.created_at >= CURRENT_TIMESTAMP - make_interval(days => %s::integer)
      AND nullif(btrim(p.niche), '') IS NOT NULL
      AND nullif(btrim(p.metro), '') IS NOT NULL
)
SELECT p.niche, p.metro,
       count(DISTINCT p.id)::integer AS prospect_count,
       count(DISTINCT q.prospect_id)::integer AS qualification_count,
       count(DISTINCT l.entity_id)::integer AS company_count,
       count(DISTINCT r.id)::integer AS reply_records_unverified,
       count(DISTINCT r.id) FILTER (
           WHERE r.classification = 'positive'
       )::integer AS positive_classified_replies_unverified
FROM recent_prospects AS p
LEFT JOIN public.prospect_qualifications AS q
    ON q.prospect_id = p.id
   AND q.scored_at >= CURRENT_TIMESTAMP - make_interval(days => %s::integer)
LEFT JOIN public.prospect_entity_links AS l
    ON l.prospect_id = p.id AND l.active IS TRUE
LEFT JOIN public.outbound_intents AS i
    ON i.prospect_id = p.id
LEFT JOIN public.outbound_replies AS r
    ON r.intent_id = i.id
   AND r.received_at >= CURRENT_TIMESTAMP - make_interval(days => %s::integer)
GROUP BY p.niche, p.metro
ORDER BY prospect_count DESC, p.niche, p.metro
LIMIT %s::integer
"""


def project_restricted_rows(
    result_rows: list[tuple[Any, ...]],
    *, window_days: int,
) -> dict[str, Any]:
    markets: list[dict[str, Any]] = []
    for row in result_rows:
        if not isinstance(row, (tuple, list)) or len(row) != 7:
            raise ValueError("unexpected restricted market row")
        niche, metro, prospects, qualifications, companies, replies, positives = row
        if not isinstance(niche, str) or not isinstance(metro, str):
            raise ValueError("invalid market grouping")
        if not niche.strip() or not metro.strip():
            raise ValueError("empty market grouping")
        values = (prospects, qualifications, companies, replies, positives)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("invalid restricted market counts")
        if positives > replies:
            raise ValueError("positive classifications exceed total replies")
        markets.append({
            "niche": niche,
            "metro": metro,
            "prospect_count": prospects,
            "acquisition_count": prospects,
            "qualification_count": qualifications,
            "scored_prospect_count": qualifications,
            "canonical_company_count": companies,
            # A row's existence or self-reported classification is not a
            # verified inbound buyer, tenant authority, or purchase intent.
            "unverified_reply_record_count": replies,
            "unverified_positive_classification_count": positives,
            "commercial_reply_count": 0,
            "commercial_terms_count": 0,
            "verified_payment_count": 0,
            "recognized_revenue_event_count": 0,
            "approved_buyer_count": 0,
            "delivered_outreach_count": 0,
            "raw_reply_records_are_commercial_proof": False,
            "source_provenance": "empiredb_restricted_market_aggregate_v1",
        })
    return {
        "schema_version": "empire.market_sweep_revenue_gps.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "markets": markets,
        "source_scope": "RESTRICTED_AGGREGATES_ONLY",
        "source_tables": [
            "prospects", "prospect_qualifications", "prospect_entity_links",
            "outbound_intents", "outbound_replies",
        ],
        "inbound_reply_authenticity_verified": False,
        "commercial_demand_verified": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "execution_authority": "none",
    }


# Diagnostics deliberately operate on countable original IDs only. The
# restricted role does not have provider_message_id, contact, subject or body.
# A matched outbound intent is NOT authentication of an inbound reply.
REPLY_LINEAGE_QUERY = """
SELECT
    count(DISTINCT r.id)::integer AS observed_reply_rows,
    count(DISTINCT r.id) FILTER (
        WHERE r.intent_id IS NOT NULL
    )::integer AS rows_with_intent_pointer,
    count(DISTINCT r.id) FILTER (
        WHERE i.id IS NOT NULL
    )::integer AS rows_matched_to_outbound_intent,
    count(DISTINCT r.id) FILTER (
        WHERE p.id IS NOT NULL
    )::integer AS rows_matched_to_prospect,
    count(DISTINCT r.id) FILTER (
        WHERE r.classification = 'positive'
    )::integer AS positive_classifications_unverified
FROM public.outbound_replies r
LEFT JOIN public.outbound_intents i ON i.id = r.intent_id
LEFT JOIN public.prospects p ON p.id = i.prospect_id
WHERE r.received_at >= CURRENT_TIMESTAMP - make_interval(days => %s::integer)
"""


def project_reply_lineage(row: Any, *, window_days: int) -> dict[str, Any]:
    if not isinstance(row, (tuple, list)) or len(row) != 5:
        raise ValueError("unexpected restricted reply-lineage aggregate")
    if type(window_days) is not int or not 1 <= window_days <= 90:
        raise ValueError("invalid bounded reply-lineage window")
    if any(type(n) is not int or n < 0 for n in row):
        raise ValueError("invalid reply-lineage counts")
    total, has_intent, matching_intent, matching_prospect, classified = row
    if not (
        matching_prospect <= matching_intent <= has_intent <= total
        and classified <= total
    ):
        raise ValueError("reply-lineage count relationship is contradictory")
    return {
        "schema": "empire.market_gps_restricted_reply_lineage.v1",
        "window_days": window_days,
        "reply_records_observed": total,
        "reply_records_with_intent_pointer": has_intent,
        "reply_records_matched_to_intent": matching_intent,
        "reply_records_matched_to_prospect": matching_prospect,
        "reply_records_missing_intent_pointer": total - has_intent,
        "reply_records_with_unmatched_intent": has_intent - matching_intent,
        "reply_records_with_unmatched_prospect": matching_intent - matching_prospect,
        "positive_classification_records_unverified": classified,
        "original_provider_message_id_checked": False,
        "canonical_contact_identity_verified": False,
        "provider_thread_binding_verified": False,
        "tenant_binding_verified": False,
        "buyer_intent_verified": False,
        "commercial_demand_inferred": False,
        "read_only_aggregate": True,
        "execution_authority": "none",
    }
