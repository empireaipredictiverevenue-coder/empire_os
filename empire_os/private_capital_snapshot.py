"""Canonical read-only Private Capital intelligence snapshot.

Only explicitly materialized private-capital-domain evidence is counted.
Generic companies, prospects, titles or model guesses are not promoted into
sponsor, portfolio, add-on, deal-intent or opportunity evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


Reader = Callable[[str, dict[str, str]], Any]


def _rows(
    reader: Reader,
    path: str,
    params: dict[str, str],
    *,
    page_size: int = 1000,
    max_pages: int = 100,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(max_pages):
        batch = reader(
            path,
            {
                **params,
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        if not isinstance(batch, list):
            raise ValueError(f"{path} returned invalid payload")
        clean = [row for row in batch if isinstance(row, dict)]
        rows.extend(clean)
        if len(batch) < page_size:
            return rows
    raise ValueError(f"{path} exceeded bounded pagination")


def _latest(values: list[Any]) -> str | None:
    clean = sorted(
        str(value).strip()
        for value in values
        if str(value or "").strip()
    )
    return clean[-1] if clean else None


def fetch_private_capital_snapshot(
    reader: Reader,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    signals = _rows(
        reader,
        "/rest/v1/intelligence_signals",
        {
            "select": "id,signal_type,signal_domain,observed_at,created_at",
            "signal_domain": "eq.private_capital",
            "order": "observed_at.asc.nullslast,created_at.asc",
        },
    )
    facts = _rows(
        reader,
        "/rest/v1/intelligence_facts",
        {
            "select": "id,fact_key,last_seen_at,created_at",
            "fact_key": "like.private_capital.%",
            "order": "last_seen_at.asc.nullslast,created_at.asc",
        },
    )
    segments = _rows(
        reader,
        "/rest/v1/intelligence_segments",
        {
            "select": "id,segment_key,intelligence_domain,active,created_at",
            "intelligence_domain": "eq.private_capital",
            "active": "eq.true",
            "order": "created_at.asc",
        },
    )

    memberships: list[dict[str, Any]] = []
    segment_ids = [
        str(row.get("id") or "").strip()
        for row in segments
        if str(row.get("id") or "").strip()
    ]
    if segment_ids:
        memberships = _rows(
            reader,
            "/rest/v1/intelligence_segment_membership",
            {
                "select": "entity_id,segment_id,scored_at",
                "segment_id": "in.(" + ",".join(segment_ids) + ")",
                "order": "scored_at.asc",
            },
        )

    latest_observed_at = _latest([
        *(row.get("observed_at") or row.get("created_at") for row in signals),
        *(row.get("last_seen_at") or row.get("created_at") for row in facts),
        *(row.get("scored_at") for row in memberships),
    ])

    now = generated_at or datetime.now(timezone.utc).isoformat()
    evidence_count = len(signals) + len(facts) + len(memberships)

    return {
        "schema_version": "empire.private-capital-snapshot.v1",
        "generated_at": now,
        "source": "canonical_supabase",
        "canonical_signal_count": len(signals),
        "canonical_fact_count": len(facts),
        "private_capital_segment_count": len(segments),
        "segment_membership_count": len(memberships),
        "latest_observed_at": latest_observed_at,
        "evidence_state": (
            "EVIDENCE_AVAILABLE" if evidence_count > 0 else "UNKNOWN"
        ),
        "deal_intent_observed": False,
        "opportunity_count": None,
        "pricing_observed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
