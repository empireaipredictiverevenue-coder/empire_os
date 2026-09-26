"""Canonical Market Sweeps / Revenue GPS runtime.

This module aggregates observed niche/metro evidence from Supabase and produces
an OBSERVE-only market map for research prioritization. It does not turn
acquisition volume, qualification scores, competitor evidence, or approved
buyer reviews into market demand, buyer intent, market share, revenue, or
execution authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.runtime_env import load_runtime_env


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/market_sweeps/revenue_gps_latest.json"
)


def _num(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _ratio(a: int, b: int) -> float | None:
    if b <= 0:
        return None
    return round(a / b, 4)


def _catalog_economics(catalog: Any) -> dict[str, Any]:
    rows = catalog if isinstance(catalog, list) else []
    row = next(
        (
            item for item in rows
            if isinstance(item, Mapping)
            and item.get("product_code") == "managed_service"
            and item.get("binding_terms_ready") is True
            and item.get("catalog_state") == "VERIFIED"
            and item.get("version_state") == "VERIFIED"
        ),
        None,
    )
    if not isinstance(row, Mapping):
        return {
            "available": False,
            "product_code": "managed_service",
            "prediction": False,
            "actual_revenue": False,
        }

    price = row.get("price_basis")
    acquisition = row.get("acquisition_cost_basis")
    fulfilment = row.get("fulfilment_cost_basis")
    price = price if isinstance(price, Mapping) else {}
    acquisition = acquisition if isinstance(acquisition, Mapping) else {}
    fulfilment = fulfilment if isinstance(fulfilment, Mapping) else {}

    price_cents = _num(price.get("amount_cents"))
    acquisition_cents = _num(acquisition.get("amount_cents"))
    fulfilment_cents = _num(fulfilment.get("amount_cents"))
    policy_cost_ceiling = acquisition_cents + fulfilment_cents

    return {
        "available": True,
        "product_code": "managed_service",
        "product_name": row.get("product_name"),
        "currency": row.get("currency"),
        "pilot_price_cents": price_cents,
        "acquisition_cost_ceiling_cents": acquisition_cents,
        "fulfilment_cost_ceiling_cents": fulfilment_cents,
        "policy_cost_ceiling_cents": policy_cost_ceiling,
        "policy_margin_at_ceiling_cents": max(
            0, price_cents - policy_cost_ceiling
        ),
        "minimum_margin_bps": _num(
            (row.get("margin_policy") or {}).get("minimum_margin_bps")
        ),
        "economics_kind": "founder_policy_scenario",
        "prediction": False,
        "actual_cost_observed": False,
        "actual_revenue": False,
    }


def _market_row(
    row: Mapping[str, Any],
    *,
    economics: Mapping[str, Any],
) -> dict[str, Any]:
    acquisitions = _num(row.get("acquisition_count"))
    qualifications = _num(row.get("qualification_count"))
    approved_buyers = _num(row.get("approved_buyer_count"))
    delivered = _num(row.get("delivered_outreach_count"))
    commercial_replies = _num(row.get("commercial_reply_count"))
    terms = _num(row.get("commercial_terms_count"))
    payments = _num(row.get("verified_payment_count"))
    recognized_events = _num(
        row.get("recognized_revenue_event_count")
    )
    canonical_companies = _num(row.get("canonical_company_count"))
    competitive_entities = _num(row.get("competitive_entity_count"))
    competitive_signals = _num(row.get("competitive_signal_count"))

    commercial_demand_evidence = (
        commercial_replies + terms + payments
    )
    competitive_density = (
        competitive_signals / canonical_companies
        if canonical_companies > 0
        else None
    )
    competitor_pressure_proxy = (
        round(min(100.0, competitive_density * 25.0), 2)
        if competitive_density is not None
        else None
    )
    coverage_gap = max(
        0, canonical_companies - competitive_entities
    )

    evidence_refs = []
    if acquisitions:
        evidence_refs.append("canonical:prospect_acquisitions")
    if qualifications:
        evidence_refs.append("canonical:prospect_qualifications")
    if approved_buyers:
        evidence_refs.append("canonical:buyer_candidate_reviews")
    if delivered:
        evidence_refs.append("canonical:outbound_events:delivered")
    if commercial_replies:
        evidence_refs.append("canonical:outbound_replies:commercial")
    if terms:
        evidence_refs.append("canonical:commercial_terms_reviews")
    if payments:
        evidence_refs.append("canonical:bsc_payment_evidence")
    if competitive_signals:
        evidence_refs.append(
            "canonical:intelligence_signals:competitive_intelligence"
        )
    if recognized_events:
        evidence_refs.append(
            "canonical:commercial_events:revenue_recognized"
        )

    # Research priority only. This is not a purchase, demand or revenue score.
    research_priority = min(
        100.0,
        round(
            min(acquisitions, 40) * 1.5
            + min(qualifications, 20) * 1.0
            + min(approved_buyers, 5) * 4.0
            + min(competitive_signals, 20) * 0.5,
            2,
        ),
    )

    product_candidate = (
        "managed_service"
        if economics.get("available") is True
        and approved_buyers > 0
        else None
    )

    return {
        "niche": str(row.get("niche") or "").strip(),
        "metro": str(row.get("metro") or "").strip(),
        "prospect_count": _num(row.get("prospect_count")),
        "canonical_company_count": canonical_companies,
        "scored_prospect_count": _num(row.get("scored_prospect_count")),
        "acquisition_count": acquisitions,
        "qualification_count": qualifications,
        "approved_buyer_count": approved_buyers,
        "delivered_outreach_count": delivered,
        "commercial_reply_count": commercial_replies,
        "commercial_terms_count": terms,
        "verified_payment_count": payments,
        "recognized_revenue_event_count": recognized_events,
        "recognized_revenue_cents": _num(
            row.get("recognized_revenue_cents")
        ),
        "realized_margin_cents": _num(
            row.get("realized_margin_cents")
        ),
        "competitive_entity_count": competitive_entities,
        "competitive_signal_count": competitive_signals,
        "competitive_evidence_coverage_gap_count": coverage_gap,
        "acquisition_to_qualification_rate": _ratio(
            qualifications, acquisitions
        ),
        "qualification_to_approved_buyer_rate": _ratio(
            approved_buyers, qualifications
        ),
        "delivered_to_commercial_reply_rate": _ratio(
            commercial_replies, delivered
        ),
        "commercial_demand_evidence_count": commercial_demand_evidence,
        "commercial_demand_state": (
            "observed"
            if commercial_demand_evidence > 0
            else "not_observed"
        ),
        "competitor_pressure_proxy": competitor_pressure_proxy,
        "competitor_pressure_basis": (
            "competitive_signal_density"
            if competitor_pressure_proxy is not None
            else "unavailable"
        ),
        "competitor_pressure_is_model": (
            competitor_pressure_proxy is not None
        ),
        "supply_gap_state": "unknown_not_measured",
        "supply_gap_inferred": False,
        "research_priority_score": research_priority,
        "research_candidate": bool(evidence_refs),
        "product_candidate": product_candidate,
        "product_candidate_basis": (
            "verified_product_plus_approved_buyer_presence"
            if product_candidate
            else None
        ),
        "product_purchase_inferred": False,
        "economics_scenario": (
            dict(economics)
            if product_candidate
            else None
        ),
        "market_revenue_prediction_cents": None,
        "evidence_refs": evidence_refs,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def normalize_market_sweep(
    raw: Mapping[str, Any],
    *,
    catalog: Any,
) -> dict[str, Any]:
    economics = _catalog_economics(catalog)
    source_rows = raw.get("markets")
    source_rows = source_rows if isinstance(source_rows, list) else []
    markets = [
        _market_row(row, economics=economics)
        for row in source_rows
        if isinstance(row, Mapping)
    ]
    markets.sort(
        key=lambda row: (
            -row["research_priority_score"],
            -row["acquisition_count"],
            row["niche"].casefold(),
            row["metro"].casefold(),
        )
    )

    demand_markets = [
        row for row in markets
        if row["commercial_demand_evidence_count"] > 0
    ]
    competitive_markets = [
        row for row in markets
        if row["competitor_pressure_proxy"] is not None
    ]

    return {
        "schema_version": "empire.market_sweep_revenue_gps.v1",
        "mode": "OBSERVE",
        "generated_at": raw.get("generated_at"),
        "window_days": _num(raw.get("window_days")) or 7,
        "market_count": len(markets),
        "commercial_demand_market_count": len(demand_markets),
        "competitive_evidence_market_count": len(competitive_markets),
        "markets": markets,
        "research_queue": [
            {
                "niche": row["niche"],
                "metro": row["metro"],
                "research_priority_score": row[
                    "research_priority_score"
                ],
                "evidence_refs": row["evidence_refs"],
                "recommended_next_action": (
                    "advance_existing_approved_buyer"
                    if row["approved_buyer_count"] > 0
                    else "deepen_market_research"
                ),
                "mutation_authorized": False,
                "external_execution_authorized": False,
            }
            for row in markets[:20]
        ],
        "verified_product_economics": economics,
        "demand_signal_semantics": (
            "only genuine commercial replies, terms and verified payments "
            "count as observed commercial demand"
        ),
        "supply_gap_semantics": (
            "unknown until a direct supply/demand observation exists"
        ),
        "competitor_pressure_semantics": (
            "modeled research proxy from observed competitive evidence "
            "density; not market share"
        ),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def fetch_market_sweep_postgres(
    dsn: str,
    *,
    window_days: int = 7,
    limit: int = 100,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    clean = str(dsn or "").strip()
    if not clean:
        raise ValueError("materializer database dsn required")
    days = max(1, min(int(window_days), 31))
    bounded = max(1, min(int(limit), 200))

    if connect_factory is None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for Market Sweep refresh"
            ) from exc
        connect_factory = psycopg.connect

    try:
        with connect_factory(clean) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                cursor.execute(
                    "SELECT public.get_market_sweep_revenue_gps(%s,%s)",
                    (days, bounded),
                )
                market_row = cursor.fetchone()
                cursor.execute(
                    "SELECT public.get_commercial_product_catalog(%s,%s)",
                    ("managed_service", 5),
                )
                catalog_row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(
            "restricted Market Sweep read failed"
        ) from exc

    raw = market_row[0] if market_row else {}
    catalog = catalog_row[0] if catalog_row else []
    if not isinstance(raw, Mapping):
        raise ValueError("Market Sweep RPC returned invalid payload")
    return normalize_market_sweep(raw, catalog=catalog)


def write_market_sweep_snapshot(
    payload: Mapping[str, Any],
    repo_root: Path,
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return path


def build_market_sweep_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.market_sweep_revenue_gps.v1",
            "mode": "OBSERVE",
            "market_count": 0,
            "commercial_demand_market_count": 0,
            "competitive_evidence_market_count": 0,
            "markets": [],
            "research_queue": [],
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "revenue_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    if not isinstance(raw, dict):
        raise ValueError("Market Sweep snapshot must be a JSON object")
    return {"available": True, **raw}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not args.refresh:
        print(json.dumps(
            build_market_sweep_runtime(root),
            indent=2,
            sort_keys=True,
        ))
        return 0

    env = load_runtime_env(
        root / "runtime/secrets/intelligence_materializer.env",
        required=("EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",),
    )
    payload = fetch_market_sweep_postgres(
        env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"],
        window_days=args.window_days,
        limit=args.limit,
    )
    path = write_market_sweep_snapshot(payload, root)
    print(json.dumps({
        "ok": True,
        "path": str(path),
        "market_count": payload["market_count"],
        "commercial_demand_market_count": payload[
            "commercial_demand_market_count"
        ],
        "competitive_evidence_market_count": payload[
            "competitive_evidence_market_count"
        ],
        "top_research_markets": [
            {
                "niche": row["niche"],
                "metro": row["metro"],
                "research_priority_score": row[
                    "research_priority_score"
                ],
                "commercial_demand_state": row[
                    "commercial_demand_state"
                ],
            }
            for row in payload["markets"][:5]
        ],
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
