#!/usr/bin/env python3
"""Existing EmpireOS Revenue Strike DFW contractor founder-review projection.

Safe by default: read-only stdout. --write writes an OBSERVE-only snapshot
to the existing runtime/revenue_strike location. Never sends or signs.
"""
from __future__ import annotations

from argparse import ArgumentParser
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

from empire_os.claims_exchange.controls import parse_date
from empire_os.storm_contractor_review import (
    build_contractor_review, attach_existing_canonical_contact_history,
)
from empire_os.storm_contractor_relationships import relationship_context
from empire_os.commercial_pricing_live_verifier import verify_catalog_snapshot

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "runtime/revenue_strike/dfw_storm_2026-09-20.json"
SITES = ROOT / "docs/DFW_SITE_OBSERVATIONS_20261009.json"
SIGNALS = ROOT / "docs/DFW_CONTRACTOR_PUBLIC_SIGNALS_20261009.json"
INDEPENDENT = ROOT / "docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json"
STATE_REGISTRY = ROOT / "docs/DFW_CONTRACTOR_TEXAS_PUBLIC_ENTITY_RESEARCH_20261010.json"
BUSINESS_CONTACT_RESEARCH = ROOT / "docs/DFW_CONTRACTOR_BUSINESS_CONTACT_RESEARCH_20261010.json"
OUTPUT = ROOT / "runtime/revenue_strike/contractor_founder_review_latest.json"
EXISTING_RELATIONSHIPS = ROOT / "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
EXISTING_CATALOG = ROOT / "runtime/commercial_catalog/latest.json"
MAX_BYTES = 1024 * 1024
CATALOG_MAX_BYTES = 3500000


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("SOURCE_MISSING_OR_UNBOUNDED")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("SOURCE_MUST_BE_OBJECT")
    return data


def _catalog_internal_provenance(review: dict, catalog: dict | None, *, now: datetime) -> dict:
    """Link one canonical product; never turn the link into sales authority.

    Product economics remain internal. First-touch copy, signing, recipient
    eligibility and all send permissions are owned by existing governance.
    """
    item = {
        "product_code": "managed_service",
        "status": "CATALOG_EVIDENCE_UNAVAILABLE",
        "offer_approved_for_these_prospects": False,
        "founder_approved_recipient": False,
        "recipient_level_suppression_cleared": False,
        "price_mention_allowed_in_first_touch": False,
        "binding_quote_created": False,
        "outbound_authorized": False,
        "contract_authorized": False,
        "execution_authority": "none",
    }
    if catalog is not None:
        if not isinstance(catalog, dict) or catalog.get("schema_version") != "empire.commercial-product-catalog.v1":
            raise ValueError("UNTRUSTED_CANONICAL_CATALOG_SCHEMA")
        rows = catalog.get("products")
        if not isinstance(rows, list) or len(rows) > 500 or catalog.get("product_count") != len(rows):
            raise ValueError("CANONICAL_CATALOG_ROW_COUNT_INVALID")
        timestamp = catalog.get("generated_at")
        try:
            stamped = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if stamped.tzinfo is None:
                raise ValueError("naive")
            elapsed = (now - stamped.astimezone(timezone.utc)).total_seconds()
        except (TypeError, AttributeError, ValueError) as exc:
            raise ValueError("UNTRUSTED_CANONICAL_CATALOG_TIMESTAMP") from exc
        matches = [row for row in rows if isinstance(row, dict) and row.get("product_code") == "managed_service"]
        if len(matches) != 1:
            raise ValueError("CANONICAL_MANAGED_SERVICE_PRODUCT_NOT_UNIQUE")
        row = matches[0]
        price = row.get("price_basis") if isinstance(row.get("price_basis"), dict) else {}
        valid = (
            -300 <= elapsed <= 72 * 3600
            and row.get("active") is True
            and row.get("catalog_state") == "VERIFIED"
            and row.get("version_state") == "VERIFIED"
            and row.get("binding_terms_ready") is True
            and row.get("readiness_blockers") == []
            and row.get("product_name") == "Empire Opportunity Intelligence Pilot"
            and row.get("currency") == "USD"
            and row.get("billing_model") == "flat_pilot"
            and price.get("amount_cents") == 150000
            and price.get("unit") == "flat"
            and price.get("currency") == "USD"
            and price.get("state") == "VERIFIED"
            and price.get("source_type") == "founder_approved"
            and price.get("approval_reference")
                == "founder_approval:first_cash_economics:2026-09-21"
            and row.get("actual_revenue") is False
            and isinstance(row.get("product_id"), str)
            and len(row["product_id"]) == 36
        )
        # Reuse existing launch-price drift check rather than introduce a
        # competing catalog/price calculator.
        pricing = verify_catalog_snapshot(catalog, observed_at=now)
        if valid and pricing.get("pricing_matches_approved_policy") is True:
            item.update({
                "status": "CATALOG_VERIFIED_INTERNAL_REFERENCE",
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "currency": "USD",
                "founder_catalog_price_cents": price["amount_cents"],
                "price_basis": "founder_approved_flat_pilot",
                "catalog_generated_at": stamped.isoformat(),
                "pricing_drift_count": pricing["drift_count"],
            })
        else:
            item["status"] = "CATALOG_UNVERIFIED_OR_PRICE_DRIFT_HOLD"
    out = deepcopy(review)
    out["existing_commercial_product"] = item
    out["summary"]["existing_catalog_offer_verified_internal"] = int(
        item["status"] == "CATALOG_VERIFIED_INTERNAL_REFERENCE"
    )
    # Never promote unqualified contacts even when product is ready.
    if (out.get("mode") != "OBSERVE"
            or out.get("outbound_authorized") is not False
            or any(p.get("outbound_authorized") is not False for p in out["packets"])
            or any(p.get("existing_outbound_rapport_policy", {}).get(
                "commercial_pricing_allowed") is not False
                for p in out["packets"])):
        raise ValueError("CATALOG_REFERENCE_CANNOT_OVERRIDE_RAPPORT_GATES")
    out["review_digest"] = sha256(json.dumps({
        "as_of": out["as_of"], "summary": out["summary"],
        "packets": out["packets"], "existing_commercial_product": item,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return out


def run(*, as_of: date, now: datetime | None = None) -> dict:
    base = build_contractor_review(
        _load(COHORT), _load(SITES), _load(SIGNALS), as_of=as_of,
        independent_evidence=_load(INDEPENDENT),
        state_registry_evidence=_load(STATE_REGISTRY),
        business_contact_research=_load(BUSINESS_CONTACT_RESEARCH),
    )
    try:
        relationships = _load(EXISTING_RELATIONSHIPS)
    except (OSError, ValueError, json.JSONDecodeError):
        relationships = None  # fail closed; no implied contact clearance
    checked_at = now or datetime.now(timezone.utc)
    reconciled = relationship_context(base, relationships, now=checked_at)
    try:
        if EXISTING_CATALOG.stat().st_size > CATALOG_MAX_BYTES:
            raise ValueError("CATALOG_SOURCE_UNBOUNDED")
        catalog = _load(EXISTING_CATALOG)
    except (OSError, ValueError, json.JSONDecodeError):
        catalog = None
    return _catalog_internal_provenance(reconciled, catalog, now=checked_at)


def write_review_snapshot(payload: dict) -> None:
    """Atomic private OBSERVE snapshot, never a CRM/database or outbound write."""
    if (payload.get("schema") != "empire.revenue_strike.contractor_founder_review.v1"
            or payload.get("mode") != "OBSERVE"
            or payload.get("outbound_authorized") is not False
            or payload.get("contract_sent") is not False
            or payload.get("execution_authority") != "none"):
        raise ValueError("UNSAFE_CONTRACTOR_SNAPSHOT_AUTHORITY")
    if OUTPUT.is_symlink() or OUTPUT.parent.is_symlink():
        raise ValueError("UNSAFE_CONTRACTOR_SNAPSHOT_LOCATION")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    filehandle, name = tempfile.mkstemp(
        prefix=".contractor_founder_", suffix=".json.tmp", dir=OUTPUT.parent,
    )
    try:
        with os.fdopen(filehandle, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(payload, f, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, OUTPUT)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv=None) -> int:
    parser = ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--write", action="store_true", help="Only write OBSERVE evidence snapshot to existing runtime")
    parser.add_argument("--check-contact-history", action="store_true",
                        help="Read EmpireDB contact history via existing owned, read-only guard; fail closed when unavailable")
    args = parser.parse_args(argv)
    try:
        effective_date = parse_date(args.as_of)
        if effective_date is None:
            raise ValueError("BAD_AS_OF_DATE")
        payload = run(as_of=effective_date)
        if args.check_contact_history:
            from scripts.materialize_company_routed_buyer_review import _canonical_contact_history
            _, prior_domains, suppressions = _canonical_contact_history()
            payload = attach_existing_canonical_contact_history(
                payload, prior_contact_domains=prior_domains,
                suppressed_emails=suppressions,
            )
        if args.write:
            write_review_snapshot(payload)
        print(json.dumps({
            "schema": payload["schema"],
            "mode": "OBSERVE",
            "summary": payload["summary"],
            "review_digest": payload["review_digest"],
            "existing_relationship_registry_state": payload.get("existing_relationship_registry_state", "UNAVAILABLE"),
            "existing_relationship_domain_matches": payload["summary"].get("existing_relationship_domain_matches", 0),
            "canonical_domain_history_observed": payload.get("canonical_domain_history_observed", False),
            "individual_recipient_suppression_cleared": False,
            "prioritized_company_research": [
                {"company": row["company_name"],
                 "score": row["research_priority_score"],
                 "stage": row["qualification"],
                 "followup_tasks": len(row["review_tasks"])}
                for row in payload["packets"]],
            "output": str(OUTPUT) if args.write else None,
            "outbound_authorized": False,
            "contract_sent": False,
            "execution_authority": "none",
        },sort_keys=True))
        return 0
    except Exception as exc:
        # Fail closed on missing DB permission/schema/transport without emitting
        # credentials, customer contacts, or a half-checked founder snapshot.
        print(json.dumps({
            "schema": "empire.revenue_strike.contractor_founder_review_failure.v1",
            "mode": "OBSERVE",
            "reason": type(exc).__name__, "status": "BLOCKED",
            "outbound_authorized": False, "contract_sent": False,
            "execution_authority": "none",
        },sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
