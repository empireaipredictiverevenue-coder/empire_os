"""Read-only, multi-product TAM portfolio projection.

Composes existing canonical TAM, Commercial Exchange and Revenue Exchange receipts.
It does not size markets from lead rosters, create leads, or grant any sales authority.
This is a projection within the existing TAM owner, not a new database or agent.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

TAM_SCHEMA = "empire.tam-market-intelligence.v1"
COMMERCIAL_SCHEMA = "empire.commercial_exchange_snapshot.v1"
REVENUE_SCHEMA = "empire.revenue_exchange.live_snapshot.v1"

# The SAME canonical company may buy multiple products, or both buy and sell leads.
# Products/roles are separate addressable motions, NOT additive company populations.
PRODUCT_LINES = (
    ("predictive_revenue_saas", "Predictive Revenue SaaS", ("subscriber", "enterprise_buyer")),
    ("enterprise_intelligence", "Predictive Cloud & Enterprise Intelligence", ("enterprise_buyer",)),
    ("leads_exchange", "Leads Exchange", ("lead_buyer", "publisher", "inventory_supplier")),
    ("pay_per_call", "Pay-per-call & Buyer Routing", ("call_buyer", "call_supplier")),
    ("data_brokerage", "Premium Data Brokerage & APIs", ("data_buyer", "data_supplier")),
    ("gtm_agency", "GTM, PR & Advisory Agency", ("services_client",)),
    ("seo_aeo_geo", "Search, SEO, AEO & GEO Intelligence", ("subscriber", "services_client")),
    ("rank_and_rent", "Rank-and-rent & Organic Demand", ("territory_buyer", "publisher")),
    ("storm_property", "Storm & Property Intelligence", ("data_buyer", "contractor", "lead_buyer")),
    ("heat_pump_eco", "Heat Pumps, Solar & ECO", ("installer", "lead_buyer", "fulfilment_partner")),
    ("jobs_contractor", "Jobs & Contractor Matching", ("employer", "contractor", "supplier")),
    ("mediaos", "MediaOS & YouTube Intelligence", ("subscriber", "agency_client")),
    ("white_label", "White-label & Partner Licensing", ("reseller", "agency_client")),
    ("affiliate_publishers", "Publisher & Affiliate Distribution", ("publisher", "affiliate")),
    ("smart_crm", "Smart CRM & Revenue Workbench", ("subscriber", "enterprise_buyer")),
    ("trading_research", "Private Trading Research (paper only)", ("research_user",)),
)

LEADS_SECTORS = frozenset((
    "roofing", "solar", "hvac", "dental", "legal", "insurance",
    "plumbing", "home_services", "general_contractor", "heat_pumps",
))
SECTOR_FIT = {
    "leads_exchange": LEADS_SECTORS,
    "pay_per_call": LEADS_SECTORS,
    "rank_and_rent": LEADS_SECTORS,
    "storm_property": frozenset(("roofing", "insurance", "storm", "property")),
    "heat_pump_eco": frozenset(("solar", "heat_pumps", "hvac", "eco")),
    "jobs_contractor": frozenset(("roofing", "solar", "hvac", "construction")),
}


def _nonnegative(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _rows(value: Any, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise ValueError(f"{field} must be an array of objects")
    return value


def _observe(data: Mapping[str, Any], schema: str, source: str | None = None) -> None:
    if data.get("schema_version") != schema or data.get("mode") != "OBSERVE":
        raise ValueError(f"{schema} source contract mismatch")
    if data.get("execution_authority") != "none":
        raise ValueError("source has unapproved execution authority")
    if source is not None and data.get("source") != source:
        raise ValueError("noncanonical source rejected")


def _age_days(value: Any, now: datetime) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp > now:
        return None
    return (now - stamp.astimezone(timezone.utc)).days


def _commercial_counts(data: Mapping[str, Any] | None) -> dict[str, Any]:
    empty = {
        "source_available": False, "inventory_rows": None,
        "distinct_inventory_prospects": None,
        "qualified_supply_prospects": None, "overflow_prospects": None,
        "blocked_inventory_rows": None, "buyer_seats": None,
        "observed_buyer_ids": None, "active_buyer_seats": None,
        "active_buyer_capacity": None, "blocked_buyer_seats": None,
        "verified_market_price_observations": None,
        "observed_at": None,
    }
    if data is None:
        return empty
    _observe(data, COMMERCIAL_SCHEMA, "canonical_empiredb_projection")
    if data.get("candidate_selection") != "qualification_driven" or data.get("actual_revenue") is not False:
        raise ValueError("Commercial Exchange provenance or revenue contract failed")
    if data.get("canonical_backend") != "empiredb":
        raise ValueError("Commercial Exchange must use canonical EmpireDB")
    inventory = _rows(data.get("inventory"), "commercial inventory")
    seats = _rows(data.get("buyer_seats"), "commercial buyer seats")
    if len(inventory) != _nonnegative(data.get("inventory_count"), "inventory_count"):
        raise ValueError("Commercial Exchange inventory count mismatch")
    if len(seats) != _nonnegative(data.get("buyer_seat_count"), "buyer_seat_count"):
        raise ValueError("Commercial Exchange seat count mismatch")
    prospect_ids = {
        str(row.get("prospect_id")).strip()
        for row in inventory if row.get("prospect_id")
    }
    supply = {
        str(row.get("prospect_id")).strip()
        for row in inventory
        if row.get("prospect_id")
        and row.get("state") in ("allocation_candidate", "overflow_no_capacity")
    }
    overflow = {
        str(row.get("prospect_id")).strip()
        for row in inventory
        if row.get("prospect_id") and row.get("state") == "overflow_no_capacity"
    }
    active_seats = [
        row for row in seats if row.get("seat_state") == "active_capacity"
    ]
    capacity = sum(
        _nonnegative(row.get("remaining_capacity"), "remaining_capacity")
        for row in active_seats
    )
    return {
        "source_available": True,
        "inventory_rows": len(inventory),
        "distinct_inventory_prospects": len(prospect_ids),
        "qualified_supply_prospects": len(supply),
        "overflow_prospects": len(overflow),
        "blocked_inventory_rows": sum(
            row.get("state") == "blocked_missing_evidence" for row in inventory
        ),
        "buyer_seats": len(seats),
        "observed_buyer_ids": len({
            str(row["buyer_id"]).strip()
            for row in seats if row.get("buyer_id")
        }),
        "active_buyer_seats": len(active_seats),
        "active_buyer_capacity": capacity,
        "blocked_buyer_seats": sum(
            row.get("seat_state") != "active_capacity" for row in seats
        ),
        "verified_market_price_observations": _nonnegative(
            data.get("verified_market_price_count"), "verified_market_price_count"
        ),
        "observed_at": data.get("observed_at"),
    }


def _revenue_counts(data: Mapping[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {
            "source_available": False, "observed_markets": None,
            "reconciled_markets": None, "generated_at": None,
        }
    _observe(data, REVENUE_SCHEMA, "canonical_empiredb_revenue_exchange_observations")
    if data.get("read_only") is not True or data.get("revenue_recognition") is not False:
        raise ValueError("Revenue Exchange readonly contract mismatch")
    rows = _rows(data.get("markets"), "revenue markets")
    if len(rows) != _nonnegative(data.get("market_count"), "revenue market count"):
        raise ValueError("Revenue Exchange market count mismatch")
    return {
        "source_available": True, "observed_markets": len(rows),
        "reconciled_markets": sum(
            row.get("reconciliation_evidence") is not None for row in rows
        ),
        "generated_at": data.get("generated_at"),
    }


def build_tam_revenue_portfolio(
    *,
    tam_snapshot: Mapping[str, Any],
    commercial_exchange_snapshot: Mapping[str, Any] | None = None,
    revenue_exchange_snapshot: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a source-backed portfolio coverage report without cross-product TAM sums."""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("now must have a timezone")
    clock = clock.astimezone(timezone.utc)
    _observe(tam_snapshot, TAM_SCHEMA, "empiredb_restricted_tam_reader")
    scopes = _rows(tam_snapshot.get("market_scopes"), "TAM market_scopes")
    if len(scopes) != _nonnegative(tam_snapshot.get("market_scope_count"), "TAM market_scope_count"):
        raise ValueError("TAM market-scope count mismatch")
    entity_ids: set[str] = set()
    sectors: Counter[str] = Counter()
    for scope in scopes:
        sector = str(scope.get("industry") or "").strip().lower()
        country = str(scope.get("country_code") or "").strip()
        if not sector or len(country) != 2:
            raise ValueError("incomplete TAM market scope")
        rows = _rows(scope.get("entities"), "TAM scope entities")
        if len(rows) != _nonnegative(scope.get("observed_entity_count"), "observed_entity_count"):
            raise ValueError("TAM scope observed count mismatch")
        ids = {str(row.get("entity_id") or "").strip() for row in rows}
        if not all(ids) or len(ids) != len(rows):
            raise ValueError("missing or duplicated TAM canonical entity")
        entity_ids.update(ids)
        sectors[sector] += len(ids)
    if len(entity_ids) != _nonnegative(
        tam_snapshot.get("observed_unique_entity_count"), "observed_unique_entity_count"
    ):
        raise ValueError("TAM unique entity count mismatch")
    exchange = _commercial_counts(commercial_exchange_snapshot)
    revenue = _revenue_counts(revenue_exchange_snapshot)
    products = []
    for product_id, label, roles in PRODUCT_LINES:
        fit = SECTOR_FIT.get(product_id)
        products.append({
            "product_id": product_id,
            "product": label,
            "commercial_roles": list(roles),
            "observed_sector_sample_rows": (
                sum(n for sector, n in sectors.items() if sector in fit)
                if fit is not None else None
            ),
            "total_addressable_companies": None,
            "serviceable_addressable_companies": None,
            "qualified_buyer_count": None,
            "revenue_potential": None,
            "market_size_state": "UNKNOWN",
            "counts_are_additive_across_products": False,
            "decision": "RESEARCH_ONLY",
        })
    age_days = _age_days(tam_snapshot.get("generated_at"), clock)
    return {
        "schema_version": "empire.tam-revenue-portfolio.v2",
        "generated_at": clock.isoformat(),
        "mode": "OBSERVE",
        "tenant_id": tam_snapshot.get("tenant_id"),
        "tam_snapshot_age_days": age_days,
        "tam_snapshot_stale": age_days is None or age_days > 7,
        "observed_unique_market_entities": len(entity_ids),
        "observed_market_scopes": len(scopes),
        "source_population_complete": False,
        "market_population_count": None,
        "tam_state": "UNKNOWN",
        "matched_customers_proven": False,
        "decision_maker_count": None,
        "verified_email_count": None,
        "company_size_enrichment_count": None,
        "company_turnover_enrichment_count": None,
        "commercial_exchange": exchange,
        "revenue_exchange": revenue,
        "product_line_count": len(products),
        "product_lines": products,
        "market_population_from_lead_roster": False,
        "exchange_buyer_seat_is_qualified_buyer": False,
        "exchange_observed_rate_is_verified_price": False,
        "revenue_verified": False,
        "prospect_created": False,
        "new_outbound_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }

def read_tam_revenue_portfolio_from_runtime(runtime_root: "str | Path") -> dict[str, Any]:
    """Compose the three existing saved receipts; no database connection or writes."""
    import json
    from pathlib import Path

    root = Path(runtime_root).resolve()
    if not root.is_dir():
        raise ValueError("canonical runtime root missing")

    def load(relative: str, required: bool = False) -> dict[str, Any] | None:
        path = root / relative
        if not path.is_file():
            if required:
                raise ValueError("canonical TAM snapshot missing")
            return None
        if path.is_symlink() or path.stat().st_size > 10_000_000:
            raise ValueError("unsafe runtime receipt")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid runtime receipt")
        return data

    return build_tam_revenue_portfolio(
        tam_snapshot=load("tam_market_intelligence/latest.json", required=True),
        commercial_exchange_snapshot=load("commercial_exchange/latest.json"),
        revenue_exchange_snapshot=load("revenue_exchange/latest.json"),
    )
