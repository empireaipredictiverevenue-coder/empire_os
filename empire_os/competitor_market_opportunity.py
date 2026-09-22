"""Competitor market coverage / opportunity projection for EmpireOS.

This module turns observed competitor-audience evidence into research coverage
gaps and territory-level heatmaps. It does not infer demand, buyer intent,
commercial intent, market share, or revenue opportunity from missing evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.competitor_audience_sweep import load_resolved_market_entities
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_market_opportunity_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def build_market_opportunity_projection(
    *,
    market_scale: Mapping[str, Any],
    resolved_entities: list[Mapping[str, Any]],
) -> dict[str, Any]:
    market_key = _clean(market_scale.get("market_key"))
    market_query = _clean(market_scale.get("market_query"))
    niche = _clean(market_scale.get("niche"))
    metro = _clean(market_scale.get("metro"))

    observed_by_entity = {
        _clean(row.get("entity_id")): row
        for row in market_scale.get("companies", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }

    audience_rows: list[dict[str, Any]] = []
    for raw in resolved_entities:
        if not isinstance(raw, Mapping):
            continue
        entity_id = _clean(raw.get("entity_id") or raw.get("id"))
        if not entity_id:
            continue

        observed = observed_by_entity.get(entity_id)
        competitor_count = (
            int(observed.get("competitor_count") or 0)
            if isinstance(observed, Mapping)
            else 0
        )
        evidence_count = (
            int(observed.get("evidence_count") or 0)
            if isinstance(observed, Mapping)
            else 0
        )

        audience_rows.append({
            "entity_id": entity_id,
            "company_name": _clean(
                raw.get("company_name") or raw.get("canonical_name")
            ),
            "company_domain": _clean(
                raw.get("company_domain") or raw.get("canonical_website")
            ),
            "observed_competitor_count": competitor_count,
            "observed_evidence_count": evidence_count,
            "evidence_coverage_state": (
                "observed"
                if evidence_count > 0
                else "not_observed"
            ),
            "research_priority": (
                "high"
                if evidence_count == 0
                else "normal"
            ),
            "reason": (
                "No competitor-audience evidence has been observed for this "
                "resolved company in the current market snapshot."
                if evidence_count == 0
                else "Competitor-audience evidence is already observed."
            ),
            "underserved_demand_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "revenue_opportunity_inferred": False,
            "outreach_enabled": False,
        })

    audience_rows.sort(
        key=lambda row: (
            row["observed_evidence_count"] > 0,
            row["company_name"].casefold(),
        )
    )

    total = len(audience_rows)
    observed = sum(
        1 for row in audience_rows
        if row["observed_evidence_count"] > 0
    )
    gaps = total - observed

    territory = {
        "territory_key": metro or market_key,
        "market_key": market_key,
        "market_query": market_query,
        "niche": niche,
        "metro": metro,
        "resolved_company_count": total,
        "company_with_competitor_evidence_count": observed,
        "company_without_competitor_evidence_count": gaps,
        "evidence_coverage_ratio": (
            round(observed / total, 4) if total else 0.0
        ),
        "observed_competitor_count": int(
            market_scale.get("competitor_with_evidence_count") or 0
        ),
        "unique_evidence_count": int(
            market_scale.get("unique_evidence_count") or 0
        ),
        "shared_audience_edge_count": int(
            market_scale.get("shared_audience_edge_count") or 0
        ),
        "heat_metric": "competitor_evidence_coverage_gap",
        "demand_heat_inferred": False,
        "market_share_inferred": False,
        "revenue_opportunity_inferred": False,
    }

    return {
        "schema_version": "empire.competitor_market_opportunity.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_key": market_key,
        "market_query": market_query,
        "niche": niche,
        "metro": metro,
        "resolved_company_count": total,
        "observed_company_count": observed,
        "research_gap_company_count": gaps,
        "underserved_audience_candidates": [
            row for row in audience_rows
            if row["observed_evidence_count"] == 0
        ],
        "all_resolved_companies": audience_rows,
        "territory_heatmap": [territory],
        "underserved_demand_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_opportunity_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def write_market_opportunity_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def refresh_market_opportunity_snapshot(
    repo_root: Path,
    writer: PostgresIntelligenceMaterializer,
) -> dict[str, Any]:
    market_scale = _load_json(
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_market_scale_latest.json"
    )
    entities = load_resolved_market_entities(
        writer,
        niche=_clean(market_scale.get("niche")),
        metro=_clean(market_scale.get("metro")),
    )
    payload = build_market_opportunity_projection(
        market_scale=market_scale,
        resolved_entities=entities,
    )
    write_market_opportunity_snapshot(repo_root, payload)
    return payload


def build_market_opportunity_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": "empire.competitor_market_opportunity.v1",
            "mode": "OBSERVE",
            "resolved_company_count": 0,
            "observed_company_count": 0,
            "research_gap_company_count": 0,
            "territory_heatmap": [],
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "revenue_opportunity_inferred": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build competitor market coverage gaps and territory heatmap"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.refresh:
        print(json.dumps(
            build_market_opportunity_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_market_opportunity_snapshot(repo_root, writer)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
