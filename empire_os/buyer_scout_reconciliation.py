"""Duplicate-safe reconciliation for Buyer Acquisition Scout results.

Matches scouted first-party domains against canonical buyers and prospects.
No database writes are performed. Unmatched companies remain external research
candidates until a separate governed ingest path is approved.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


OUTPUT = Path("runtime/buyer_acquisition/reconciliation_latest.json")


def _host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(
        text if "://" in text else "https://" + text
    )
    host = parsed.netloc.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _domain_index(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        host = _host(row.get("website"))
        if not host:
            continue
        index.setdefault(host, []).append(row)
    return index


def reconcile_scout_candidates(
    scout: Mapping[str, Any],
    *,
    prospects: Iterable[Mapping[str, Any]],
    buyers: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    prospect_index = _domain_index(prospects)
    buyer_index = _domain_index(buyers)

    results: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for raw in scout.get("candidates") or []:
        if not isinstance(raw, Mapping):
            continue
        candidate = dict(raw)
        domain = _host(
            candidate.get("website")
            or candidate.get("domain")
        )
        if not domain:
            state = "BLOCKED_NO_DOMAIN"
            matches: list[dict[str, Any]] = []
        elif domain in buyer_index:
            state = "EXISTING_CANONICAL_BUYER"
            matches = [
                {
                    "buyer_id": row.get("id"),
                    "business_name": row.get("buyer_name"),
                    "status": row.get("status"),
                    "is_active": row.get("is_active"),
                }
                for row in buyer_index[domain]
            ]
        elif domain in prospect_index:
            state = "EXISTING_CANONICAL_PROSPECT"
            matches = [
                {
                    "prospect_id": row.get("id"),
                    "business_name": row.get("business_name"),
                    "status": row.get("status"),
                    "niche": row.get("niche"),
                    "metro": row.get("metro"),
                }
                for row in prospect_index[domain]
            ]
        else:
            state = "NEW_EXTERNAL_BUYER_CANDIDATE"
            matches = []

        counts[state] += 1
        results.append({
            "domain": domain or None,
            "business_name": candidate.get("business_name"),
            "buyer_type": candidate.get("buyer_type"),
            "direct_buyer_score": candidate.get(
                "direct_buyer_score"
            ),
            "target_buyer_pools": list(
                candidate.get("target_buyer_pools") or []
            ),
            "target_product_codes": list(
                candidate.get("target_product_codes") or []
            ),
            "target_corridor_keys": list(
                candidate.get("target_corridor_keys") or []
            ),
            "reconciliation_state": state,
            "canonical_matches": matches,
            "automatic_ingest_authorized": False,
            "outreach_authorized": False,
        })

    results.sort(
        key=lambda row: (
            str(row["reconciliation_state"]),
            -int(row.get("direct_buyer_score") or 0),
            str(row.get("domain") or ""),
        )
    )

    return {
        "schema_version": "empire.buyer_scout_reconciliation.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(results),
        "reconciliation_state_counts": dict(sorted(counts.items())),
        "existing_buyer_count": int(
            counts.get("EXISTING_CANONICAL_BUYER", 0)
        ),
        "existing_prospect_count": int(
            counts.get("EXISTING_CANONICAL_PROSPECT", 0)
        ),
        "new_external_candidate_count": int(
            counts.get("NEW_EXTERNAL_BUYER_CANDIDATE", 0)
        ),
        "results": results,
        "database_write_performed": False,
        "automatic_ingest_authorized": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def write_reconciliation(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
