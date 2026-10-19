"""Loopback-only Founder API for lead counts, sources, lanes and seats."""
from __future__ import annotations

from pathlib import Path
import json

from fastapi import APIRouter

from empire_os.lead_territory_mrr_bridge import build_territory_mrr_bridge
from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory


DEFAULT_EXCHANGE = Path("/srv/empire_os/runtime/commercial_exchange/latest.json")
DEFAULT_REPORT = Path("/srv/empire_os/runtime/lead_supply/niche_counts_latest.json")


def read_lead_supply_report(path: Path = DEFAULT_REPORT) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "available": False,
            "mode": "OBSERVE",
            "reason": "canonical_lead_supply_report_not_published",
            "lead_counts_complete": False,
            "public_self_serve_raw_lead_counts_allowed": False,
            "execution_authority": "none",
        }
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "empire.lead_supply_intelligence.v1"
        or payload.get("canonical_backend") != "empiredb"
        or payload.get("mode") != "OBSERVE"
    ):
        return {
            "available": False,
            "mode": "OBSERVE",
            "reason": "lead_supply_report_not_canonical",
            "lead_counts_complete": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def read_territory_package_preview(
    exchange_path: Path = DEFAULT_EXCHANGE,
) -> dict:
    """Nonbinding current catalogue + existing exchange capacity, no DB reads."""
    try:
        exchange = json.loads(exchange_path.read_text(encoding="utf-8"))
        if not isinstance(exchange, dict) or exchange.get("source") != "canonical_empiredb_projection":
            raise ValueError("exchange snapshot not canonical")
        projection = build_territory_mrr_bridge(exchange=exchange)
        return {"available": True, **projection}
    except (OSError, ValueError, TypeError):
        return {
            "available": False,
            "mode": "OBSERVE",
            "reason": "canonical_exchange_snapshot_unavailable",
            "actual_mrr_cents": None,
            "subscription_entitlement_verified": False,
            "execution_authority": "none",
        }


def read_lead_exchange_inventory(
    exchange_path: Path = DEFAULT_EXCHANGE,
) -> dict:
    """Founder-loopback-only safe, fresh canonical Exchange inventory view."""
    try:
        if not exchange_path.is_file() or exchange_path.stat().st_size > 5_000_000:
            raise ValueError("exchange_snapshot_not_found_or_unbounded")
        snapshot = json.loads(exchange_path.read_text(encoding="utf-8"))
        result = build_lead_exchange_live_inventory(snapshot)
        return {"available": result["state"] != "HOLD", **result}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {
            "available": False,
            "mode": "READ_ONLY_EXCHANGE_SNAPSHOT",
            "state": "HOLD",
            "reason": "canonical_exchange_snapshot_unavailable",
            "delivery_ready_now": 0,
            "public_inventory_claim_allowed": False,
            "outbound_authorized": False,
            "execution_authority": "none",
        }


def create_founder_lead_supply_router(
    report_path: Path = DEFAULT_REPORT,
    exchange_path: Path = DEFAULT_EXCHANGE,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-lead-supply",
        tags=["founder-lead-supply"],
    )

    @router.get("/overview")
    def overview():
        return read_lead_supply_report(report_path)

    @router.get("/inventory")
    def inventory():
        # This route is only mounted on the existing loopback Founder read API.
        # It is NOT part of the public marketplace, and reveals no prospect IDs.
        return read_lead_exchange_inventory(exchange_path)

    @router.get("/packages")
    def packages():
        # The standalone catalogue/corridor preview remains useful even before
        # a separate protected EmpireDB read-only census has been released.
        report = read_lead_supply_report(report_path)
        if report.get("available") is True:
            existing = report.get("territory_mrr")
            if isinstance(existing, dict) and existing.get("canonical_backend") == "empiredb":
                return {"available": True, **existing}
        return read_territory_package_preview(exchange_path)

    return router
