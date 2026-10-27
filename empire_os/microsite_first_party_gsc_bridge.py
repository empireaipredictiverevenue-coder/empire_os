"""Read-only bridge from the original SEO-owned weekly GSC receipt to microsite proposals.

First-party query/page evidence is not nationwide keyword volume or city-specific
buyer demand. No search calls, no DB writes, no mapping between ZIPs and markets.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.predictive_microsite_factory import build_candidate

GSC_SCHEMA = "empire.search.weekly_keyword_intent_evidence.v1"
GSC_OWNER = "empire_os.search_intelligence.search_console"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _verify_weekly_receipt(receipt: Mapping[str, Any]) -> None:
    if (not isinstance(receipt, Mapping)
            or receipt.get("schema_version") != GSC_SCHEMA
            or receipt.get("owner") != GSC_OWNER
            or receipt.get("mode") != "READ_ONLY"
            or receipt.get("execution_authority") != "none"
            or receipt.get("database_writes") is not False
            or receipt.get("outbound_sent") is not False
            or receipt.get("publishing_authorized") is not False
            or receipt.get("market_search_volume") is not None
            or receipt.get("customer_leads_qualified") is not None
            or receipt.get("sale_or_revenue_verified") is not False
            or not isinstance(receipt.get("market_reviews"), list)):
        raise ValueError("weekly first-party GSC source schema/authority invalid")
    d = receipt.get("as_of")
    try:
        date.fromisoformat(d)
    except (TypeError, ValueError) as exc:
        raise ValueError("weekly GSC as_of missing or invalid") from exc
    for theme in receipt["market_reviews"]:
        if not isinstance(theme, Mapping) or not _text(theme.get("market_key")):
            raise ValueError("GSC market theme invalid")
        if not isinstance(theme.get("observed_exact_query_page_evidence"), list):
            raise ValueError("GSC exact query evidence must be list")
        if theme.get("real_market_keyword_volume") is not None:
            raise ValueError("GSC market volume is not verified")
        if theme.get("buyer_willingness_to_pay_verified") is not False:
            raise ValueError("GSC theme cannot claim a paying buyer")
        observations = theme["observed_exact_query_page_evidence"]
        count = theme.get("first_party_exact_query_matches")
        if count is not None and (type(count) is not int or count < 0
                                  or len(observations) > count):
            raise ValueError("GSC exact match counter inconsistent")
        for observation in observations:
            if (not isinstance(observation, Mapping)
                    or not _text(observation.get("keyword"))
                    or not isinstance(observation.get("page_evidence"), list)
                    or not observation["page_evidence"]):
                raise ValueError("GSC observation missing exact query/page evidence")


def read_existing_weekly_receipt(path: Path) -> tuple[dict[str, Any], str]:
    """Pinned caller-provided path to the original SEO-owned private receipt."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("GSC source file missing or symlink")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 1024 * 1024:
        raise ValueError("GSC source size invalid")
    receipt = json.loads(raw)
    _verify_weekly_receipt(receipt)
    return receipt, sha256(raw).hexdigest()


def connect_factory_to_gsc(
    specs: Sequence[Mapping[str, Any]], receipt: Mapping[str, Any],
    *, receipt_sha256: str | None = None,
) -> dict[str, Any]:
    """Never let a source receipt turn research into a verified local offer."""
    _verify_weekly_receipt(receipt)
    if not isinstance(specs, Sequence) or len(specs) > 25:
        raise ValueError("expected at most 25 microsite candidate specs")
    observations: dict[str, list[dict[str, Any]]] = {}
    themes = {theme["market_key"]: theme for theme in receipt["market_reviews"]}
    if len(themes) != len(receipt["market_reviews"]):
        raise ValueError("ambiguous repeated GSC theme key")
    for theme in themes.values():
        for row in theme["observed_exact_query_page_evidence"]:
            keyword = _text(row["keyword"]).casefold()
            observations.setdefault(keyword, []).append({
                "market_key": theme["market_key"],
                "page_evidence": row["page_evidence"],
            })
    results = []
    for spec in specs:
        proposal, _ = build_candidate(spec)
        keyword = proposal["keyword"]["record"]["keyword"]
        rows = observations.get(keyword.casefold(), [])
        # GSC query page association is for own domain, NOT proof of locale
        # or payment. Caller must independently provide source-backed geo.
        results.append({
            "candidate_id": proposal["id"], "keyword": keyword,
            "territory_key": proposal["market"]["market_id"],
            "first_party_query_observed": bool(rows),
            "observed_owned_query_page_pairs": len(rows),
            "gsc_first_party_evidence": rows[:10],
            "matched_themes": sorted({row["market_key"] for row in rows}),
            "geo_demand_from_gsc_proven": False,
            "buyer_accepted": False,
            "market_search_volume": None,
            "published": False,
            "next_action": ("REVIEW_REAL_QUERY_PAGE_AND_LOCALE_SOURCES"
                            if rows else "COLLECT_FIRST_PARTY_QUERY_OR_INDEPENDENT_SERP_EVIDENCE"),
        })
    return {
        "schema_version": "empire.microsite.first_party_gsc_bridge.v1",
        "mode": "OBSERVE",
        "source_owner": GSC_OWNER,
        "source_as_of": receipt["as_of"],
        "source_receipt_sha256": receipt_sha256,
        "source_status": receipt.get("source_status"),
        "source_query_page_rows": receipt.get("original_query_page_rows_returned"),
        "candidates": results,
        "candidates_with_exact_first_party_query": sum(r["first_party_query_observed"] for r in results),
        "market_volume_assumed": False,
        "local_demand_verified_from_gsc": False,
        "publication_authorized": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
