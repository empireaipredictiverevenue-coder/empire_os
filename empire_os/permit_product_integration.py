"""Permit Intelligence product/runtime integration foundation (architecture delta).

Diagram: acquisition inbox -> permit opportunity -> buyer/product match ->
         economics assessment -> recurring feed/API assessment -> read consumer.
Owner: Permit Intelligence / revenue intelligence, under Control Fabric OBSERVE.
This extends permit_intelligence_runtime's supply summary with typed, scoped
assessments for Astra/Founder read surfaces; it does not replace acquisition,
buyer-demand ownership, the commercial catalog, or EmpireDB business truth.

Contract: permit rows are public OBSERVED source evidence, never prospect IDs.
Buyer, economics and delivery inputs are caller-supplied canonical projections,
scoped to tenant/product/market (and buyer for economics/delivery). They require
OBSERVED evidence refs and a current [observed_at, valid_until) interval. Match
and readiness are INFERRED assessments, never verified commercial outcomes.
Unscoped public permits may be projected for a tenant; explicitly foreign rows
are rejected. Tenant authorization remains the calling read surface's duty.
No persistence, DB access, network, jobs, outbound, terms acceptance, payments,
revenue recognition or authority expansion. Generic DB roles gain no powers.

Execution: synchronous pure assessment, deterministic ordering/deduplication;
conflicting source identities fail closed. No retries, queues or concurrency
ownership. The optional inbox reader reports dependency loss and can recover on
its next invocation. Blockers and source refs provide read-surface diagnostics;
no fabricated demand, prices, margins, cadence or operational health.
Worker: one Codex builder owns this module and its focused tests. Verification:
focused failure/recovery and authority tests plus adjacent runtime regressions.
Rollback: remove this unused adapter; no data rollback needed. Live canonical
and Founder-surface verification is a separate promotion gate, not claimed here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from empire_os.permit_intelligence_runtime import PERMIT_SOURCES

PRODUCT_CODE = "permit_intelligence"
PRODUCT_KEY = "permit_intelligence_feed"
SOURCE_STORE = "runtime/acquisition/signal_inbox.json"


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        return result.astimezone(timezone.utc) if result.tzinfo and result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _refs(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not value or not all(_text(v) for v in value):
        return ()
    return tuple(sorted(set(v.strip() for v in value)))


def _url(value: Any) -> str | None:
    value = _text(value)
    try:
        parsed = urlsplit(value or "")
        return value if parsed.scheme in {"http", "https"} and parsed.hostname else None
    except ValueError:
        return None


@dataclass(frozen=True)
class PermitOpportunity:
    source: str
    source_record_id: str
    market: str | None
    observed_at: str
    evidence_refs: tuple[str, ...]
    signal_status: str | None
    evidence_class: str = "OBSERVED"
    opportunity_type: str = "permit_project"
    product_key: str = PRODUCT_KEY


@dataclass(frozen=True)
class BuyerProductMatch:
    buyer_id: str
    market: str
    evidence_refs: tuple[str, ...]
    capacity_remaining: int | None
    product_code: str = PRODUCT_CODE
    evidence_class: str = "INFERRED"


@dataclass(frozen=True)
class EconomicsReadiness:
    buyer_id: str
    market: str
    ready: bool
    amount_cents: int | None
    cost_cents: int | None
    currency: str | None
    unit: str | None
    margin_cents: int | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class FeedAPIReadiness:
    buyer_id: str
    market: str
    recurring_feed_ready: bool
    api_ready: bool
    cadence: str | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class PermitProductIntegration:
    tenant_id: str
    opportunities: tuple[PermitOpportunity, ...]
    buyer_product_matches: tuple[BuyerProductMatch, ...]
    economics: tuple[EconomicsReadiness, ...]
    delivery: tuple[FeedAPIReadiness, ...]
    blockers: tuple[str, ...]
    schema_version: str = "empire.permit-product-integration.v1"
    product_key: str = PRODUCT_KEY
    mode: str = "OBSERVE"
    evidence_class: str = "INFERRED"
    canonical_backend: str = "empiredb"
    execution_authority: str = "none"
    actual_revenue: bool = False
    live_delivery_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _current(row: Mapping[str, Any], now: datetime) -> bool:
    start, end = _time(row.get("observed_at")), _time(row.get("valid_until"))
    return bool(row.get("evidence_class") == "OBSERVED" and _refs(row.get("evidence_refs"))
                and start and end and start <= now < end)


def _scope(row: Mapping[str, Any], tenant: str, market: str, buyer: str | None = None) -> bool:
    return (row.get("tenant_id") == tenant and row.get("product_code") == PRODUCT_CODE
            and row.get("market") == market
            and (buyer is None or row.get("buyer_id") == buyer))


def _cents(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _one(rows: tuple[Mapping[str, Any], ...], tenant: str, match: BuyerProductMatch,
         now: datetime) -> Mapping[str, Any]:
    candidates = [r for r in rows if _scope(r, tenant, match.market, match.buyer_id) and _current(r, now)]
    # Duplicate identical snapshots are harmless; differing active snapshots are ambiguous.
    if candidates and all(r == candidates[0] for r in candidates):
        return candidates[0]
    return {}


def build_permit_product_integration(
    *, tenant_id: str, permit_signals: Iterable[Mapping[str, Any]], as_of: datetime,
    buyer_evidence: Iterable[Mapping[str, Any]] = (),
    economics_evidence: Iterable[Mapping[str, Any]] = (),
    delivery_evidence: Iterable[Mapping[str, Any]] = (),
) -> PermitProductIntegration:
    """Assess supplied evidence without materializing or activating anything.

    Buyer evidence must explicitly set demand_confirmed=True. Economics must
    supply amount_cents and cost_cents on the same currency/unit basis, plus an
    approval_reference. Delivery requires explicit contract/health booleans;
    feed and API readiness describe evidence, never permission to execute.
    """
    tenant = _text(tenant_id)
    now = _time(as_of)
    if not tenant or now is None:
        raise ValueError("tenant_id and timezone-aware as_of required")
    blockers: set[str] = set()
    opportunities: dict[tuple[str, str], PermitOpportunity] = {}
    conflicts: set[tuple[str, str]] = set()
    for row in permit_signals:
        if not isinstance(row, Mapping):
            blockers.add("invalid_permit_row")
            continue
        source = _text(row.get("source"))
        if source not in PERMIT_SOURCES:
            continue
        if row.get("tenant_id") not in (None, tenant):
            blockers.add("permit_tenant_mismatch")
            continue
        raw = row.get("raw")
        raw = raw if isinstance(raw, Mapping) else {}
        record_id = next((_text(raw.get(k)) for k in ("permit_id", "application_id", "job__", "id")
                          if _text(raw.get(k))), None)
        observed = _time(row.get("last_seen_at") or row.get("created_at"))
        url = _url(row.get("url"))
        if (row.get("evidence_class", "OBSERVED") != "OBSERVED" or not record_id
                or observed is None or observed > now or not url):
            blockers.add("permit_provenance_invalid")
            continue
        opportunity = PermitOpportunity(source, record_id, _text(row.get("metro")),
                                        observed.isoformat(), (url,), _text(row.get("status")))
        key = (source, record_id)
        if key in opportunities and opportunities[key] != opportunity:
            conflicts.add(key)
        opportunities[key] = opportunity
    for key in conflicts:
        del opportunities[key]
        blockers.add("conflicting_permit_identity")
    if not opportunities:
        blockers.add("permit_evidence_missing")
    markets = {o.market for o in opportunities.values() if o.market}
    matches: dict[tuple[str, str], BuyerProductMatch] = {}
    ambiguous: set[tuple[str, str]] = set()
    for row in buyer_evidence:
        if not isinstance(row, Mapping):
            blockers.add("buyer_evidence_invalid")
            continue
        buyer, market = _text(row.get("buyer_id")), _text(row.get("market"))
        if not (buyer and market in markets and _scope(row, tenant, market)
                and _current(row, now) and row.get("demand_confirmed") is True):
            blockers.add("buyer_evidence_unmatched_or_invalid")
            continue
        capacity = _cents(row.get("capacity_remaining"))
        match = BuyerProductMatch(buyer, market, _refs(row.get("evidence_refs")), capacity)
        key = (buyer, market)
        if key in matches and matches[key] != match:
            ambiguous.add(key)
        matches[key] = match
    for key in ambiguous:
        del matches[key]
        blockers.add("conflicting_buyer_evidence")
    if not matches:
        blockers.add("buyer_demand_unknown")
    econ_rows = tuple(r for r in economics_evidence if isinstance(r, Mapping))
    feed_rows = tuple(r for r in delivery_evidence if isinstance(r, Mapping))
    economics, delivery = [], []
    for key in sorted(matches):
        match = matches[key]
        econ = _one(econ_rows, tenant, match, now)
        amount, cost = _cents(econ.get("amount_cents")), _cents(econ.get("cost_cents"))
        currency, unit = _text(econ.get("currency")), _text(econ.get("unit"))
        errors = []
        if amount is None:
            errors.append("price_unknown")
        if cost is None:
            errors.append("cost_unknown")
        if not currency or not unit:
            errors.append("currency_or_unit_unknown")
        if not _text(econ.get("approval_reference")):
            errors.append("commercial_approval_missing")
        economics.append(EconomicsReadiness(
            match.buyer_id, match.market, not errors, amount, cost, currency, unit,
            amount - cost if amount is not None and cost is not None and currency and unit else None,
            _refs(econ.get("evidence_refs")), tuple(errors)))
        feed = _one(feed_rows, tenant, match, now)
        errors = []
        cadence = _text(feed.get("cadence"))
        for field in ("source_refresh_verified", "delivery_contract_confirmed", "delivery_health_verified"):
            if feed.get(field) is not True:
                errors.append(field + "_missing")
        if not cadence:
            errors.append("cadence_unknown")
        if match.capacity_remaining is None:
            errors.append("buyer_capacity_unknown")
        elif match.capacity_remaining == 0:
            errors.append("buyer_capacity_full")
        feed_ready = not errors
        for field in ("api_contract_verified", "tenant_access_verified"):
            if feed.get(field) is not True:
                errors.append(field + "_missing")
        delivery.append(FeedAPIReadiness(match.buyer_id, match.market, feed_ready,
                                         not errors, cadence, _refs(feed.get("evidence_refs")), tuple(errors)))
    return PermitProductIntegration(
        tenant, tuple(opportunities[k] for k in sorted(opportunities)),
        tuple(matches[k] for k in sorted(matches)), tuple(economics), tuple(delivery),
        tuple(sorted(blockers)))


def build_permit_product_runtime(repo_root: Path, *, tenant_id: str, as_of: datetime,
                                 **evidence: Any) -> PermitProductIntegration:
    """Read the existing public acquisition inbox; never fall back to another store."""
    try:
        inbox = json.loads((Path(repo_root) / SOURCE_STORE).read_text(encoding="utf-8"))
        if not isinstance(inbox, dict):
            raise ValueError("inbox must be an object")
    except (OSError, ValueError, UnicodeError):
        result = build_permit_product_integration(
            tenant_id=tenant_id, permit_signals=(), as_of=as_of, **evidence)
        from dataclasses import replace
        return replace(result, blockers=tuple(sorted((*result.blockers, "signal_inbox_unavailable"))))
    return build_permit_product_integration(
        tenant_id=tenant_id, permit_signals=inbox.values(), as_of=as_of, **evidence)
