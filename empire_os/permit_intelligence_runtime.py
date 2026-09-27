"""Read-only Permit Intelligence runtime projection.

Builds product-readiness evidence from the durable acquisition signal inbox.
It never creates prospects, sends outreach, prices products or mutates signals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PERMIT_SOURCES = {
    "permits",
    "permits_nyc",
    "building_permits",
    "planning_permits",
}


def _load_inbox(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        str(key): row
        for key, row in value.items()
        if isinstance(row, dict)
    }


def _is_permit_signal(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "").strip().lower()
    return source in PERMIT_SOURCES or "permit" in source


def build_permit_intelligence_runtime(repo_root: Path) -> dict[str, Any]:
    inbox_path = repo_root / "runtime" / "acquisition" / "signal_inbox.json"
    inbox = _load_inbox(inbox_path)
    rows = [row for row in inbox.values() if _is_permit_signal(row)]

    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_metro: dict[str, int] = {}
    latest_seen_at: str | None = None
    with_source_url = 0
    with_raw_reference = 0

    for row in rows:
        status = str(row.get("status") or "unknown")
        source = str(row.get("source") or "unknown")
        metro = str(row.get("metro") or "").strip()

        by_status[status] = by_status.get(status, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
        if metro:
            by_metro[metro] = by_metro.get(metro, 0) + 1

        seen = str(row.get("last_seen_at") or row.get("created_at") or "").strip()
        if seen and (latest_seen_at is None or seen > latest_seen_at):
            latest_seen_at = seen

        if str(row.get("url") or "").strip():
            with_source_url += 1

        raw = row.get("raw")
        if isinstance(raw, dict) and any(
            raw.get(key) not in (None, "")
            for key in ("id", "job__", "permit_id", "application_id")
        ):
            with_raw_reference += 1

    resolved = int(by_status.get("resolved") or 0)
    unresolved = int(by_status.get("unresolved") or 0)
    evidence_available = bool(rows)

    return {
        "schema_version": "empire.permit-intelligence-runtime.v1",
        "mode": "OBSERVE",
        "product_key": "permit_intelligence_feed",
        "evidence_state": (
            "EVIDENCE_AVAILABLE" if evidence_available else "UNKNOWN"
        ),
        "signal_count": len(rows),
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "by_status": dict(sorted(by_status.items())),
        "by_source": dict(sorted(by_source.items())),
        "by_metro": dict(sorted(by_metro.items())),
        "latest_seen_at": latest_seen_at,
        "with_source_url": with_source_url,
        "with_raw_reference": with_raw_reference,
        "source_store": "runtime/acquisition/signal_inbox.json",
        "canonical_product_contract": "permit_intelligence_feed",
        "read_surface_ready": evidence_available,
        "pricing_observed": False,
        "binding_terms_ready": False,
        "payment_observed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
