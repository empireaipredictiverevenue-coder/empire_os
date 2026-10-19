"""Loopback-only Founder API for lead counts, sources, lanes and seats."""
from __future__ import annotations

from pathlib import Path
import json

from fastapi import APIRouter

from empire_os.lead_territory_mrr_bridge import build_territory_mrr_bridge
from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from empire_os.official_source_canonical_preflight import preflight_official_source_ledgers
from empire_os.leadgen_revenue_activation_queue import build_leadgen_revenue_queue
from empire_os.buyer_specification_readiness import build_buyer_specification_readiness


DEFAULT_EXCHANGE = Path("/srv/empire_os/runtime/commercial_exchange/latest.json")
DEFAULT_REPORT = Path("/srv/empire_os/runtime/lead_supply/niche_counts_latest.json")
DEFAULT_BUYER_ACTIONS = Path("/srv/empire_os/runtime/buyer_network_intelligence/founder_qualification_actions_latest.json")
DEFAULT_RELATIONSHIPS = Path("/srv/empire_os/runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
DEFAULT_SOURCE_LEDGERS = {
    "gb_recc_solar": Path("/srv/empire_os/runtime/lead_supply/private_recc_sweeps/internal_observations.json"),
    "us_cms_nppes_dental_npi2": Path("/srv/empire_os/runtime/lead_supply/private_us_dental_orgs/organizations.json"),
    "us_nyc_dcwp_home_improvement_companies": Path("/srv/empire_os/runtime/lead_supply/private_nyc_contractors/private_business_observations.json"),
}


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


def read_official_source_readiness(paths: dict[str, Path] | None = None) -> dict:
    """Privacy-safe separate source-to-canonical preparation counts only."""
    try:
        selected = paths if paths is not None else DEFAULT_SOURCE_LEDGERS
        ledgers = {}
        for key, file in selected.items():
            if not file.is_file() or file.stat().st_size > 200_000:
                raise ValueError("source_ledger_unavailable")
            ledgers[key] = json.loads(file.read_text(encoding="utf-8"))
        result = preflight_official_source_ledgers(ledgers)
        return {"available": True, **result}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {
            "available": False,
            "mode": "OFFICIAL_TO_CANONICAL_REVIEW_ONLY",
            "state": "HOLD",
            "reason": "source_readiness_ledger_unavailable",
            "verified_net_new_empiredb_prospects": 0,
            "exchange_inventory_added": 0,
            "outbound_authorized": False,
            "execution_authority": "none",
        }


def read_founder_leadgen_queue(
    exchange_path: Path = DEFAULT_EXCHANGE,
    buyer_path: Path = DEFAULT_BUYER_ACTIONS,
    relationship_path: Path | None = None,
) -> dict:
    """PRIVATE loopback API: verified source-ledger research, never send authority."""
    try:
        data = {}
        for name, path in (("exchange", exchange_path), ("buyer_actions", buyer_path)):
            if not path.is_file() or path.stat().st_size > 5_000_000:
                raise ValueError("buyer_or_exchange_snapshot_missing_or_oversized")
            data[name] = json.loads(path.read_text(encoding="utf-8"))
        if relationship_path is not None:
            if (not relationship_path.is_file()
                    or relationship_path.stat().st_size > 5_000_000):
                raise ValueError("canonical_relationship_registry_unavailable")
            data["relationship_history"] = json.loads(
                relationship_path.read_text(encoding="utf-8")
            )
        result = build_leadgen_revenue_queue(**data, max_visible=12)
        return {"available": result.get("state") == "FOUNDER_RESEARCH_QUEUE_READY", **result}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {
            "available": False,
            "mode": "READ_ONLY_PRIVATE_LEADGEN",
            "state": "HOLD",
            "reason": "founder_leadgen_evidence_unavailable",
            "qualified_buyers": 0,
            "ready_for_outbound": 0,
            "canonical_empiredb_writes": False,
            "buyer_outreach_authorized": False,
            "execution_authority": "none",
        }


def read_buyer_specification_gap_board(
    exchange_path: Path = DEFAULT_EXCHANGE,
    relationship_path: Path = DEFAULT_RELATIONSHIPS,
) -> dict:
    """Existing partner and canonical Exchange review, no execution."""
    try:
        result = build_buyer_specification_readiness(
            exchange=json.loads(exchange_path.read_text(encoding="utf-8")),
            relationships=json.loads(relationship_path.read_text(encoding="utf-8")),
        )
        return {"available": result.get("state") == "FOUNDER_PARTNER_GAP_BOARD_READY", **result}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {"available": False, "state": "HOLD",
                "verified_buyer_specifications": 0,
                "commercial_activation_authorized": False,
                "outbound_authorized": False,
                "canonical_empiredb_writes": False,
                "execution_authority": "none"}


def create_founder_lead_supply_router(
    report_path: Path = DEFAULT_REPORT,
    exchange_path: Path = DEFAULT_EXCHANGE,
    source_ledger_paths: dict[str, Path] | None = None,
    buyer_actions_path: Path = DEFAULT_BUYER_ACTIONS,
    relationship_path: Path | None = DEFAULT_RELATIONSHIPS,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-lead-supply",
        tags=["founder-lead-supply"],
    )

    @router.get("/overview")
    def overview():
        return read_lead_supply_report(report_path)

    @router.get("/leadgen")
    def leadgen():
        return read_founder_leadgen_queue(
            exchange_path, buyer_actions_path, relationship_path
        )

    @router.get("/buyer-specifications")
    def buyer_specifications():
        return read_buyer_specification_gap_board(exchange_path, relationship_path)

    @router.get("/source-readiness")
    def source_readiness():
        # Private founder aggregate. No company names, licence numbers,
        # source URLs or contact data exposed, and no canonical DB write.
        return read_official_source_readiness(source_ledger_paths)

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
