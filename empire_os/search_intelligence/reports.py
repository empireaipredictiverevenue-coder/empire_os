"""Deterministic client-report contracts for Search Growth products.

Reports only organize supplied/observed evidence. Missing sections remain
explicitly unavailable; no metrics, findings or commercial outcomes are
fabricated.
"""
from __future__ import annotations

from typing import Any, Mapping

from .products import get_search_product


def build_search_product_report(
    *,
    product_key: str,
    site: str,
    generated_at: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    product = get_search_product(product_key)
    if product is None:
        raise ValueError("search product not found")

    target_site = str(site or "").strip()
    if not target_site:
        raise ValueError("site required")
    timestamp = str(generated_at or "").strip()
    if not timestamp:
        raise ValueError("generated_at required")
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence must be an object")

    sections: list[dict[str, Any]] = []
    observed = 0
    unavailable = 0
    for deliverable in product.deliverables:
        has_value = (
            deliverable in evidence
            and evidence.get(deliverable) is not None
        )
        if has_value:
            observed += 1
            sections.append({
                "key": deliverable,
                "state": "observed",
                "evidence": evidence.get(deliverable),
            })
        else:
            unavailable += 1
            sections.append({
                "key": deliverable,
                "state": "unavailable",
                "evidence": None,
                "reason": "no_observed_evidence_supplied",
            })

    coverage = (
        round(observed / len(sections), 4)
        if sections
        else 0.0
    )
    return {
        "schema_version": "empire.search.client-report.v1",
        "product": product.as_dict(),
        "site": target_site,
        "generated_at": timestamp,
        "evidence_coverage": coverage,
        "observed_sections": observed,
        "unavailable_sections": unavailable,
        "sections": sections,
        "commercial_terms_required": True,
        "pricing_observed": False,
        "execution_allowed": False,
        "publishing_execution": False,
        "indexation_execution": False,
        "synthetic_metrics": 0,
        "limitations": [
            "report_organizes_observed_evidence_only",
            "missing_sections_remain_unavailable",
            "no_rank_traffic_revenue_or_authority_invention",
        ],
    }
