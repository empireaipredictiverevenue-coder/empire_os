"""Buyer Scout + Jev: two public supplier requests, evidence and feasibility only."""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path

from empire_os.jev_b2b_counterparty_readiness import audit_public_b2b_counterparties

ROOT=Path("/srv/empire_os")
PUBLIC=Path("docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_CANDIDATES_20261022.json")
CAPACITY=ROOT/"runtime/buyer_capacity_readiness/latest.json"
ROUTE=ROOT/"runtime/revenue/lead_smart/ringba/routing_observation/latest.json"
OUTPUT=Path("docs/commercial/JEV_B2B_SUPPLIER_REQUESTS_COUNTERPARTY_READINESS_20261022.json")


def _bounded(file:Path,limit:int)->dict|None:
    try:
        if (file.is_symlink() or not file.is_file()
            or not 0<file.stat().st_size<=limit):
            return None
        row=json.loads(file.read_text())
        return row if isinstance(row,dict) else None
    except (OSError,ValueError,TypeError,UnicodeError):
        return None


def current_review(*,at:datetime)->dict:
    repo=Path(__file__).resolve().parents[1]
    original_file=repo/PUBLIC
    records=_bounded(original_file,50000)
    if records is None:
        raise ValueError("original dated public-source ledger unavailable")
    out=audit_public_b2b_counterparties(
        records,buyer_capacity=_bounded(CAPACITY,100000),
        existing_roofing_route=_bounded(ROUTE,200000),
        as_of=at,
    )
    out["original_public_manual_source_sha256"]=sha256(original_file.read_bytes()).hexdigest()
    out["original_public_reddit_business_identity_independently_proven"]=False
    out["production_and_source_snapshots_not_mutated"]=True
    return out


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    dest=repo/OUTPUT
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("refuse overwrite of original commercial-counterparty review")
    out=current_review(at=datetime.now(timezone.utc))
    with dest.open("x",encoding="utf8") as f:
        json.dump(out,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":out["status"],
        "cases":out["counterparties_assessed"],
        "buyer_identity_verified":out["verified_named_buyer_companies"],
        "buyer_capacity":out["buyer_scout_aggregate_status"],
        "organic_supply_ready":out["ready_to_deliver"],
        "outreach":out["outbound_sent"],
        "crm_writes":out["crm_writes"],
    },sort_keys=True))


if __name__=="__main__":
    main()
