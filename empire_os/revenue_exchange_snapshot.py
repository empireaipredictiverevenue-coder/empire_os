"""Canonical read-only Revenue Exchange runtime snapshot materializer."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.revenue_exchange import normalise_exchange_snapshot


SCHEMA_VERSION = "empire.revenue_exchange.live_snapshot.v1"
DEFAULT_OUTPUT = Path("runtime/revenue_exchange/latest.json")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    raw = _clean(value)
    return raw or None


def _when(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        raw = _clean(value)
        if not raw:
            raise ValueError("observed_at required")
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    return result.astimezone(timezone.utc)


def _evidence(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _reconciliation_evidence(evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    refs = tuple(dict.fromkeys(
        _clean(ref)
        for ref in (evidence.get("evidence_refs") or ())
        if _clean(ref)
    ))
    required = (
        "inventory_count",
        "buyer_capacity",
        "verified_prices_cents",
    )
    if not refs or any(evidence.get(field) is None for field in required):
        return None
    try:
        inventory = int(evidence["inventory_count"])
        capacity = int(evidence["buyer_capacity"])
        prices = tuple(int(value) for value in evidence["verified_prices_cents"])
    except (TypeError, ValueError):
        return None
    if inventory < 0 or capacity < 0 or any(value <= 0 for value in prices):
        return None
    return {
        "inventory_count": inventory,
        "buyer_capacity": capacity,
        "verified_prices_cents": list(prices),
        "evidence_refs": list(refs),
    }


def build_revenue_exchange_live_snapshot(
    rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must include timezone")

    latest: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
    invalid: list[dict[str, Any]] = []

    for index, raw in enumerate(rows):
        row = dict(raw or {})
        try:
            snap = normalise_exchange_snapshot(row)
            observed = _when(row.get("observed_at"))
        except (TypeError, ValueError) as exc:
            invalid.append({
                "row_index": index,
                "observation_key": _clean(row.get("observation_key")) or None,
                "reason": str(exc),
            })
            continue

        evidence = _evidence(row.get("evidence"))
        independent = _reconciliation_evidence(evidence)
        market_key = (snap.niche.casefold(), snap.metro.casefold())
        market = {
            "market_key": f"{snap.niche.casefold()}::{snap.metro.casefold()}",
            "observation_key": _clean(row.get("observation_key")) or None,
            "snapshot": snap.as_dict(),
            "source": snap.source,
            "evidence": evidence,
            "created_at": _iso(row.get("created_at")),
            "reconciliation_evidence": independent,
            "blockers": (
                [] if independent is not None
                else ["independent_reconciliation_evidence_missing"]
            ),
        }
        previous = latest.get(market_key)
        if previous is None or observed > previous[0]:
            latest[market_key] = (observed, market)

    markets = [item[1] for item in latest.values()]
    markets.sort(key=lambda item: item["market_key"])
    blockers: list[str] = []
    if not markets:
        blockers.append("no_revenue_exchange_observations")
    if invalid:
        blockers.append("invalid_revenue_exchange_rows_present")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "source": "canonical_empiredb_revenue_exchange_observations",
        "mode": "OBSERVE",
        "market_count": len(markets),
        "invalid_row_count": len(invalid),
        "blocker_count": len(blockers),
        "markets": markets,
        "invalid_rows": invalid,
        "blockers": blockers,
        "read_only": True,
        "execution_authority": "none",
        "allocation_authority": "none",
        "pricing_authority": "none",
        "settlement_authority": "none",
        "payment_action": False,
        "revenue_recognition": False,
    }


def write_revenue_exchange_live_snapshot(
    repo_root: str | Path,
    payload: Mapping[str, Any],
    *,
    output: str | Path = DEFAULT_OUTPUT,
) -> Path:
    root = Path(repo_root).resolve()
    target = Path(output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
