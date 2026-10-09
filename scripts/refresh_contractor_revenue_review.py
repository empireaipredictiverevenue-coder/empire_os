#!/usr/bin/env python3
"""Existing EmpireOS Revenue Strike DFW contractor founder-review projection.

Safe by default: read-only stdout. --write writes an OBSERVE-only snapshot
to the existing runtime/revenue_strike location. Never sends or signs.
"""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import date, datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "runtime/revenue_strike/dfw_storm_2026-09-20.json"
SITES = ROOT / "docs/DFW_SITE_OBSERVATIONS_20261009.json"
SIGNALS = ROOT / "docs/DFW_CONTRACTOR_PUBLIC_SIGNALS_20261009.json"
INDEPENDENT = ROOT / "docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json"
STATE_REGISTRY = ROOT / "docs/DFW_CONTRACTOR_TEXAS_PUBLIC_ENTITY_RESEARCH_20261010.json"
OUTPUT = ROOT / "runtime/revenue_strike/contractor_founder_review_latest.json"
EXISTING_RELATIONSHIPS = ROOT / "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
MAX_BYTES = 1024 * 1024


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("SOURCE_MISSING_OR_UNBOUNDED")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("SOURCE_MUST_BE_OBJECT")
    return data


def run(*, as_of: date, now: datetime | None = None) -> dict:
    base = build_contractor_review(
        _load(COHORT), _load(SITES), _load(SIGNALS), as_of=as_of,
        independent_evidence=_load(INDEPENDENT),
        state_registry_evidence=_load(STATE_REGISTRY),
    )
    try:
        relationships = _load(EXISTING_RELATIONSHIPS)
    except (OSError, ValueError, json.JSONDecodeError):
        relationships = None  # fail closed; no implied contact clearance
    return relationship_context(
        base, relationships, now=now or datetime.now(timezone.utc),
    )


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
