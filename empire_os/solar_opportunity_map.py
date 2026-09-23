"""Evidence-backed £249 Solar Opportunity Map artifact.

This is an internal materialization step. It reuses Empire Search Intelligence,
Tag Intelligence and canonical buyer-review evidence. Missing search-query,
rank, traffic or competitor evidence remains unavailable; nothing is invented.

No outbound, buyer approval, payment mutation or revenue recognition occurs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
import urllib.parse

from empire_os.qualification_worker_v2 import (
    SCORING_ENGINE,
    SCORING_VERSION,
    request_json,
)
from empire_os.search_intelligence.crawler_product import crawl_search_site
from empire_os.search_intelligence.reports import build_search_product_report
from empire_os.tag_intelligence import review_tag_intelligence
from empire_os.tag_intelligence_probe import observe_tag_surface


Request = Callable[..., Any]
ARTIFACT_ROOT = Path(os.getenv(
    "EMPIRE_SOLAR_OPPORTUNITY_MAP_DIR",
    "/srv/empire_os/runtime/solar_opportunity_maps",
))

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _get(
    request: Request,
    path: str,
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request("GET", f"{path}?{query}") or []
    if not isinstance(rows, list):
        raise ValueError(f"{path} projection must be a list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def fetch_map_context(
    prospect_id: str,
    *,
    request: Request = request_json,
) -> dict[str, Any]:
    pid = str(prospect_id or "").strip()
    if not pid:
        raise ValueError("prospect_id required")

    prospects = _get(
        request,
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,niche,metro,website,phone,address,"
                "contacted_status,status,created_at"
            ),
            "id": f"eq.{pid}",
            "limit": 1,
        },
    )
    if not prospects:
        raise ValueError("canonical prospect not found")
    prospect = prospects[0]

    qualifications = _get(
        request,
        "/rest/v1/prospect_qualifications",
        {
            "select": (
                "prospect_id,score,tier,status,evidence_confidence,"
                "result_payload,scored_at"
            ),
            "prospect_id": f"eq.{pid}",
            "scoring_engine": f"eq.{SCORING_ENGINE}",
            "scoring_version": f"eq.{SCORING_VERSION}",
            "order": "scored_at.desc",
            "limit": 1,
        },
    )

    acquisitions = _get(
        request,
        "/rest/v1/prospect_acquisitions",
        {
            "select": "source,source_url,evidence,created_at",
            "prospect_id": f"eq.{pid}",
            "order": "created_at.desc",
            "limit": 5,
        },
    )

    reviews = _get(
        request,
        "/rest/v1/buyer_candidate_reviews",
        {
            "select": (
                "id,prospect_id,contact_name,contact_title,contact_email,"
                "offer_key,company_score,decision_score,evidence,status,proposed_at"
            ),
            "prospect_id": f"eq.{pid}",
            "order": "proposed_at.desc",
            "limit": 1,
        },
    )
    if not reviews:
        raise ValueError("buyer review proposal required")

    return {
        "prospect": prospect,
        "qualification": qualifications[0] if qualifications else None,
        "acquisitions": acquisitions,
        "buyer_review": reviews[0],
    }


def _priority_backlog(
    crawl: Mapping[str, Any],
    tag_review: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    audit = crawl.get("audit")
    if isinstance(audit, Mapping):
        for finding in audit.get("findings") or []:
            if not isinstance(finding, Mapping):
                continue
            rows.append({
                "source": "empire_search_crawler",
                "code": finding.get("code"),
                "severity": finding.get("severity"),
                "surface": finding.get("scope"),
                "finding": finding.get("message"),
                "recommended_action": (
                    "Review and repair the observed issue using the cited URL/evidence."
                ),
                "url": finding.get("url"),
                "evidence": finding.get("evidence") or [],
                "execution_allowed": False,
            })

    for issue in tag_review.get("issues") or []:
        if not isinstance(issue, Mapping):
            continue
        rows.append({
            "source": "empire_tag_intelligence",
            "code": issue.get("code"),
            "severity": issue.get("severity"),
            "surface": issue.get("surface"),
            "finding": issue.get("evidence"),
            "recommended_action": issue.get("recommended_action"),
            "manual_review_required": bool(
                issue.get("manual_review_required")
            ),
            "execution_allowed": False,
        })

    rows.sort(key=lambda item: (
        SEVERITY_ORDER.get(str(item.get("severity") or "").lower(), 9),
        str(item.get("source") or ""),
        str(item.get("code") or ""),
    ))
    return rows[:20]


def build_solar_opportunity_map(
    prospect_id: str,
    *,
    request: Request = request_json,
    crawl: Callable[..., Mapping[str, Any]] = crawl_search_site,
    observe_tags: Callable[..., Mapping[str, Any]] = observe_tag_surface,
) -> dict[str, Any]:
    context = fetch_map_context(prospect_id, request=request)
    prospect = context["prospect"]
    website = str(prospect.get("website") or "").strip()
    if not website:
        raise ValueError("verified first-party website required")

    crawl_result = dict(crawl(
        website,
        max_pages=10,
        request_timeout=6.0,
        time_budget_seconds=45.0,
    ))

    tag_observation = dict(observe_tags(
        website,
        request_timeout=8.0,
    ))
    if tag_observation.get("ok") is True:
        tag_review_obj = review_tag_intelligence(
            page_tags=tag_observation.get("page_tags") or {},
            measurement_tags=tag_observation.get("measurement_tags") or {},
            expectations={
                "intended_public": True,
                "schema_expected": True,
                "google_analytics_expected": True,
                "required_events": ["generate_lead"],
                "consent_review_required": True,
                "revenue_attribution_expected": True,
            },
        )
        tag_review = tag_review_obj.as_dict()
    else:
        tag_review = {
            "available": False,
            "issues": [],
            "reason": tag_observation.get("error") or "tag_observation_unavailable",
            "mode": "OBSERVE",
            "execution_authority": "none",
        }

    backlog = _priority_backlog(crawl_result, tag_review)
    qualification = context.get("qualification") or {}
    review = context["buyer_review"]
    acquisitions = context.get("acquisitions") or []

    opportunity_evidence = {
        "canonical_prospect_id": prospect.get("id"),
        "business_name": prospect.get("business_name"),
        "niche": prospect.get("niche"),
        "metro": prospect.get("metro"),
        "website": website,
        "qualification": {
            "score": qualification.get("score"),
            "tier": qualification.get("tier"),
            "status": qualification.get("status"),
            "evidence_confidence": qualification.get("evidence_confidence"),
        } if qualification else None,
        "source_provenance": [
            {
                "source": row.get("source"),
                "source_url": row.get("source_url"),
                "created_at": row.get("created_at"),
            }
            for row in acquisitions
        ],
        "buyer_review": {
            "review_id": review.get("id"),
            "status": review.get("status"),
            "contact_name": review.get("contact_name"),
            "contact_title": review.get("contact_title"),
            "contact_route": (
                (review.get("evidence") or {}).get("contact_route")
                if isinstance(review.get("evidence"), Mapping)
                else None
            ),
            "company_score": review.get("company_score"),
            "decision_score": review.get("decision_score"),
        },
        "crawl_audit": crawl_result.get("audit"),
        "tag_intelligence": tag_review,
        "serp_evidence": {
            "state": "unavailable",
            "reason": "no_live_serp_snapshot_supplied_to_map",
        },
        "synthetic_metrics": 0,
    }

    report = build_search_product_report(
        product_key="search_opportunity_map",
        site=website,
        generated_at=datetime.now(timezone.utc).isoformat(),
        evidence={
            "priority_backlog": backlog,
            "opportunity_evidence": opportunity_evidence,
        },
    )

    return {
        "schema_version": "empire.solar-opportunity-map.v1",
        "mode": "INTERNAL_MATERIALIZE",
        "offer": {
            "product_code": "solar_opportunity_map",
            "product_name": "Solar Opportunity Map",
            "currency": "GBP",
            "price_minor_units": 24900,
            "price_display": "£249",
            "commercial_state": "working_founder_agreed_offer",
            "catalog_binding": False,
        },
        "prospect": {
            "id": prospect.get("id"),
            "business_name": prospect.get("business_name"),
            "website": website,
            "niche": prospect.get("niche"),
            "metro": prospect.get("metro"),
        },
        "buyer_review": {
            "id": review.get("id"),
            "status": review.get("status"),
            "contact_name": review.get("contact_name"),
            "contact_title": review.get("contact_title"),
            "contact_email": review.get("contact_email"),
            "contact_route": (
                (review.get("evidence") or {}).get("contact_route")
                if isinstance(review.get("evidence"), Mapping)
                else None
            ),
        },
        "site_crawl": crawl_result,
        "tag_observation": tag_observation,
        "tag_review": tag_review,
        "search_opportunity_report": report,
        "priority_backlog": backlog,
        "artifact_ready": True,
        "review_approval_granted": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
        "execution_authority": "internal_artifact_only",
        "limitations": [
            "serp_query_rank_competitor_sections_require_live_observed_evidence",
            "no_traffic_lead_conversion_or_revenue_metrics_invented",
            "buyer_review_approval_remains_separate",
            "price_not_yet_bound_to_canonical_commercial_catalog",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    prospect = payload.get("prospect") or {}
    buyer = payload.get("buyer_review") or {}
    report = payload.get("search_opportunity_report") or {}
    lines = [
        f"# Solar Opportunity Map — {prospect.get('business_name') or 'Unknown business'}",
        "",
        f"**Website:** {prospect.get('website') or 'Unavailable'}",
        f"**Offer:** {payload.get('offer', {}).get('price_display', '£249')} Solar Opportunity Map",
        f"**Buyer route:** {buyer.get('contact_name') or 'Unavailable'} — {buyer.get('contact_title') or 'Unavailable'} ({buyer.get('contact_route') or 'unavailable'})",
        "",
        "## Evidence coverage",
        "",
        f"- Observed report sections: {report.get('observed_sections', 0)}",
        f"- Unavailable report sections: {report.get('unavailable_sections', 0)}",
        f"- Synthetic metrics: {report.get('synthetic_metrics', 0)}",
        "",
        "## Priority actions",
        "",
    ]
    backlog = payload.get("priority_backlog") or []
    if not backlog:
        lines.append("- No evidence-backed repair actions were observed in this bounded run.")
    else:
        for index, item in enumerate(backlog, 1):
            lines.append(
                f"{index}. **{str(item.get('severity') or 'unknown').upper()} — "
                f"{item.get('code') or 'finding'}**: "
                f"{item.get('finding') or 'Observed issue'}. "
                f"{item.get('recommended_action') or ''}".rstrip()
            )

    lines.extend([
        "",
        "## Search opportunity coverage",
        "",
    ])
    for section in report.get("sections") or []:
        state = str(section.get("state") or "unknown")
        lines.append(
            f"- **{section.get('key')}** — {state}"
            + (
                f" ({section.get('reason')})"
                if section.get("reason")
                else ""
            )
        )

    lines.extend([
        "",
        "## Truth boundary",
        "",
        "- This map contains observed evidence only.",
        "- Missing SERP/rank/traffic/competitor evidence remains unavailable.",
        "- No forecast, send, payment request or proposal is recognized as revenue.",
        "- Buyer approval and outbound remain separate governed actions.",
        "",
    ])
    return "\n".join(lines)


def write_solar_opportunity_map(
    payload: Mapping[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, str]:
    prospect = payload.get("prospect") or {}
    pid = str(prospect.get("id") or "").strip()
    if not pid:
        raise ValueError("prospect id required for artifact write")
    target_root = Path(root or ARTIFACT_ROOT)
    target_root.mkdir(parents=True, exist_ok=True)

    json_path = target_root / f"{pid}.json"
    md_path = target_root / f"{pid}.md"

    json_tmp = json_path.with_suffix(".json.tmp")
    md_tmp = md_path.with_suffix(".md.tmp")
    json_tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_tmp.write_text(
        render_markdown(payload) + "\n",
        encoding="utf-8",
    )
    os.chmod(json_tmp, 0o600)
    os.chmod(md_tmp, 0o600)
    json_tmp.replace(json_path)
    md_tmp.replace(md_path)
    os.chmod(json_path, 0o600)
    os.chmod(md_path, 0o600)
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }
