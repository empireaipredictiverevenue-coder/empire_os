"""Evidence-scoped niche × product acquisition segmentation for Predictive Cloud.

Owner-provided observations remain unverified until canonical outcome reconciliation.
No training, model promotion, contacts, payments, or outbound.
"""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Mapping, Sequence
from empire_os.acquisition_pool_qualification import qualify_pool

def segment_pool(*, lane: str, records: Sequence[Mapping]) -> dict:
    qualification = qualify_pool(lane=lane, records=records)
    segments = defaultdict(lambda: {"discovered": 0, "qualified_for_review": 0,
                                     "contact_review_ready": 0})
    for original, assessment in zip(records, qualification["records"]):
        niche = original.get("niche")
        product = original.get("product_code")
        niche = niche.strip().lower() if isinstance(niche, str) and niche.strip() and len(niche) <= 80 else "unclassified"
        product = product.strip().lower() if isinstance(product, str) and product.strip() and len(product) <= 80 else "unclassified"
        key = (niche, product)
        item = segments[key]
        item["discovered"] += 1
        item["qualified_for_review"] += int(assessment["status"] == "QUALIFIED_FOR_REVIEW")
        item["contact_review_ready"] += int(assessment["contact_review_ready"])
    return {
        "schema_version": "empire.acquisition_segment_learning.v1",
        "mode": "OBSERVE",
        "lane": lane,
        "segments": [
            {"niche": niche, "product_code": product, **count,
             "settled_revenue": None, "verified_conversion_rate": None,
             "learning_eligible": False}
            for (niche, product), count in sorted(segments.items())
        ],
        "evidence_status": "RESEARCH_OBSERVATIONS_ONLY",
        "canonical_outcomes_connected": False,
        "model_training_authorized": False,
        "model_promotion_authorized": False,
        "crm_writes": False,
    }
