"""Read-only execution adapters for the public Empire Agent Web."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from empire_os.commercial_product_catalog import public_catalog_projection

SNAPSHOT_PATH = Path(os.getenv(
    "EMPIRE_AGENT_WEB_SNAPSHOT",
    "/srv/empire_os/runtime/agent_web/canonical_snapshot.json",
))
CATALOG_SNAPSHOT_PATH = Path(os.getenv(
    "EMPIRE_COMMERCIAL_CATALOG_LATEST",
    "/srv/empire_os/runtime/commercial_catalog/latest.json",
))


def load_snapshot() -> dict[str, Any]:
    try:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        snapshot = {
            "generated_at": None,
            "counts": {},
            "markets": [],
            "seo_keywords": [],
        }
    if not isinstance(snapshot, dict):
        snapshot = {
            "generated_at": None,
            "counts": {},
            "markets": [],
            "seo_keywords": [],
        }
    try:
        catalog = json.loads(
            CATALOG_SNAPSHOT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        catalog = {
            "schema_version": "empire.commercial-product-catalog.v1",
            "products": [],
            "product_count": 0,
            "binding_terms_ready_count": 0,
        }
    snapshot["commercial_catalog"] = (
        catalog if isinstance(catalog, dict) else {"products": []}
    )
    return snapshot


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _market_score(row: dict[str, Any]) -> float:
    qual = float(row.get("avg_qualification_score") or 0)
    signal = min(float(row.get("avg_buy_signal") or 0), 100.0)
    volume = min(100.0, math.log10(max(float(row.get("prospect_count") or 1), 1)) / 3 * 100)
    rating = min(100.0, float(row.get("avg_rating") or 0) / 5 * 100)
    return round(qual * .45 + signal * .25 + volume * .20 + rating * .10, 2)


def _market_rows(snapshot: dict[str, Any], niche: str, metro: str) -> list[dict[str, Any]]:
    n, m = _norm(niche), _norm(metro)
    exact = [r for r in snapshot.get("markets", []) if _norm(r.get("niche")) == n and _norm(r.get("metro")) == m]
    if exact:
        return exact
    return [r for r in snapshot.get("markets", []) if _norm(r.get("niche")) == n]


def execute_public_capability(name: str, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = load_snapshot()
    provenance = {
        "source": snapshot.get("source", "canonical snapshot"),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "privacy": snapshot.get("privacy", "aggregated_public_safe"),
    }

    if name == "market.search":
        rows = _market_rows(snapshot, args.get("niche", ""), args.get("metro", ""))
        return {"capability": name, "markets": rows[:10], "count": len(rows), "provenance": provenance}

    if name == "market.forecast":
        rows = _market_rows(snapshot, args.get("niche", ""), args.get("metro", ""))
        return {
            "capability": name,
            "horizon_days": int(args.get("horizon_days", 30)),
            "baseline": rows[:5],
            "direction": "insufficient_time_series",
            "note": "Current canonical snapshot is real; directional forecasting needs temporal history before a trend is asserted.",
            "provenance": provenance,
        }

    if name == "opportunity.search":
        rows = _market_rows(snapshot, args.get("niche", ""), args.get("metro", ""))
        min_score = float(args.get("min_score", 60))
        limit = max(1, min(int(args.get("limit", 10)), 25))
        scored = []
        for row in rows:
            item = dict(row)
            item["opportunity_score"] = _market_score(row)
            item["score_type"] = "modeled_market_score"
            if item["opportunity_score"] >= min_score:
                scored.append(item)
        scored.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return {
            "capability": name,
            "opportunities": scored[:limit],
            "count": len(scored),
            "scope": "aggregated_market_only_no_prospect_identity",
            "provenance": provenance,
        }

    if name == "growth.seo.audit":
        kws = sorted(snapshot.get("seo_keywords", []), key=lambda r: (float(r.get("total_revenue") or 0), int(r.get("intent_score") or 0)), reverse=True)
        return {
            "capability": name,
            "status": "historical_keyword_intelligence_live",
            "url": args.get("url"),
            "top_revenue_keywords": kws[:10],
            "url_specific_crawl": "pending_adapter",
            "provenance": provenance,
        }

    if name in {"growth.aeo.audit", "growth.geo.visibility", "citation.search"}:
        return {
            "capability": name,
            "status": "coverage_pending",
            "note": "Public schema is live; evidence collection adapter is not yet wired, so no visibility or citation claim is fabricated.",
            "provenance": provenance,
        }

    if name == "product.catalog":
        public = public_catalog_projection(
            snapshot.get("commercial_catalog") or {}
        )
        return {
            "capability": name,
            **public,
            "provenance": provenance,
        }

    return {"error": "unknown_public_capability", "capability": name}
