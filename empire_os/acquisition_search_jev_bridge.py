"""Read-only Search/Jev/GTM opportunity handoff to acquisition learning.

Consumes the existing GTM observer's admissible research handoffs and preserves
their unverified nature. No parallel search engine, Jev agent, or CRM.
"""
from __future__ import annotations
from collections import Counter
from collections.abc import Mapping

def summarize_search_jev_acquisition(gtm_observation: Mapping) -> dict:
    if not isinstance(gtm_observation, Mapping):
        raise ValueError("GTM observation required")
    if gtm_observation.get("schema_version") == "empire.gtm.integration_observer.v1":
        if (gtm_observation.get("mode") != "OBSERVE"
            or gtm_observation.get("authority") != "none"
            or gtm_observation.get("execution_authority") != "none"
            or gtm_observation.get("outreach_sent") is not False
            or gtm_observation.get("crm_write_performed") is not False):
            raise ValueError("canonical non-executing GTM observation required")
        handoffs = gtm_observation.get("handoffs")
    else:
        # Backwards-compatible isolated research fixtures only.
        handoffs = gtm_observation.get("opportunities", gtm_observation.get("incoming"))
    # Fail closed if the owning observer's output shape isn't supported.
    if not isinstance(handoffs, list) or len(handoffs) > 50:
        raise ValueError("bounded canonical GTM handoffs required")
    by_source = Counter()
    by_product = Counter()
    observed_research = []
    for row in handoffs:
        if not isinstance(row, Mapping) or row.get("status") != "INTERNAL_RESEARCH_REVIEW_ONLY" or row.get("outbound_authorized") is not False or row.get("buyer_identity_verified") is not False:
            raise ValueError("only unpromoted canonical research handoffs accepted")
        source = row.get("source")
        product = row.get("product_key") or "unclassified"
        if not isinstance(source, str) or not source or not isinstance(product, str):
            raise ValueError("valid source and product required")
        by_source[source] += 1
        by_product[product[:80]] += 1
        observed_research.append({
            "handoff_ref": row.get("handoff_id"),
            "source": source,
            "product_code": product[:80],
            "niche": "unclassified",
            "qualification_status": "RESEARCH_ONLY",
            "buyer_identity_verified": False,
            "contact_authorized": False,
        })
    return {
        "schema_version": "empire.acquisition.search_jev_bridge.v1",
        "mode": "OBSERVE",
        "research_handoff_count": len(handoffs),
        "source_counts": dict(sorted(by_source.items())),
        "product_counts": dict(sorted(by_product.items())),
        "research_queue": observed_research,
        "qualification_status": "REQUIRES_INDEPENDENT_BUYER_EVIDENCE",
        "jev_inference_not_buyer_proof": True,
        "outbound_authorized": False,
        "crm_writes": False,
        "model_training_authorized": False,
        "verified_revenue": None,
    }
