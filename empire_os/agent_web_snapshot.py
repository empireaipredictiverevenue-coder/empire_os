"""Canonical Agent Web OBSERVE producer; never refresh from a prior artifact."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import urlsplit

from empire_os.intelligence_materializer_transport import PostgresIntelligenceMaterializer, ROLE
from empire_os.search_fabric.search import search

# Allow unavailable markets without scanning all 100; each call may try multiple
# Search Fabric providers, so cap the per-snapshot budget at ten market attempts.
MAX_SEARCH_MARKET_ATTEMPTS = 10
TARGET_SEARCH_OBSERVATIONS = 3

class MarketObservationsUnavailable(ValueError):
    """Canonical database observations could not be obtained."""


class FreshPublicSearchUnavailable(ValueError):
    """Search Fabric could not supply valid fresh public evidence."""


def observe_markets(writer: PostgresIntelligenceMaterializer) -> list[dict[str, Any]]:
    with writer._connect(writer.dsn, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout='15s'")
            cursor.execute("SET LOCAL ROLE " + ROLE)
            cursor.execute("""
                SELECT p.niche, p.metro, count(*) AS prospect_count,
                       avg(p.rating) AS avg_rating,
                       avg(q.score) AS avg_qualification_score,
                       avg(q.market_fit_score) AS avg_market_fit
                FROM public.prospects p
                LEFT JOIN LATERAL (
                    SELECT score, market_fit_score FROM public.prospect_qualifications
                    WHERE prospect_id=p.id AND scoring_engine='empire_os.lead_scoring'
                      AND scoring_version IN ('v1','v2')
                    ORDER BY scored_at DESC, id DESC LIMIT 1
                ) q ON true
                WHERE p.niche IS NOT NULL AND p.metro IS NOT NULL
                GROUP BY p.niche,p.metro
                ORDER BY count(*) DESC,p.niche,p.metro LIMIT 100
            """)
            names = [column.name for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def build_snapshot(markets: list[dict], *, search_fn=search) -> dict:
    if not markets:
        raise MarketObservationsUnavailable("canonical market observations unavailable")
    observations = []
    attempts = 0
    for market in markets[:MAX_SEARCH_MARKET_ATTEMPTS]:
        query = f"{market['niche']} {market['metro']}"
        attempts += 1
        try:
            result = search_fn(query, num=5, engine=None, use_cache=False)
        except Exception:
            continue
        if not isinstance(result, dict):
            continue
        params = result.get("searchParameters")
        if (not isinstance(params, dict) or result.get("error")
                or params.get("cache") is not False
                or params.get("stale") or result.get("stale")
                or params.get("synthetic") or result.get("synthetic")):
            continue
        rows = []
        organic = result.get("organic")
        for row in organic if isinstance(organic, list) else []:
            if not isinstance(row, dict) or row.get("synthetic"):
                continue
            url = row.get("link")
            if not isinstance(url, str) or any(char.isspace() for char in url):
                continue
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    continue
                if parsed.username or parsed.password:
                    continue
                parsed.port  # Reject malformed ports as well as malformed hosts.
            except ValueError:
                continue
            rows.append({"url": url, "title": row.get("title"), "position": row.get("position")})
        if not rows:
            continue
        observations.append({"query": query, "engine": params.get("engine"), "results": rows,
                             "observed_at": datetime.now(timezone.utc).isoformat()})
        if len(observations) == TARGET_SEARCH_OBSERVATIONS:
            break
    if not observations:
        raise FreshPublicSearchUnavailable("fresh public search unavailable")
    normalized = []
    for market in markets:
        normalized.append({key: (float(value) if value is not None and key.startswith('avg_') else value)
                           for key, value in market.items()})
    return {
        "schema_version": "empire.agent-web-snapshot.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "empiredb_current_aggregate_and_public_search_fabric",
        "privacy": "aggregated_public_safe", "ok": True,
        "execution_authority": "none", "outreach_enabled": False,
        "counts": {"markets": len(markets), "search_queries": len(observations),
                   "search_attempts": attempts,
                   "search_unavailable": attempts - len(observations)},
        "markets": normalized, "market_scope": "top_100_owned_inventory_markets",
        "seo_keywords": [], "seo_keyword_metrics_status": "unknown",
        "search_observations": observations,
        "buyer_intent_inferred": False, "revenue_inferred": False,
    }


def refresh_snapshot(path: Path, writer: PostgresIntelligenceMaterializer, *, search_fn=search) -> dict:
    try:
        markets = observe_markets(writer)
    except Exception:
        raise MarketObservationsUnavailable("canonical market observations unavailable") from None
    snapshot = build_snapshot(markets, search_fn=search_fn)
    # Serialize completely before touching the destination; failure preserves it.
    encoded = json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return snapshot
