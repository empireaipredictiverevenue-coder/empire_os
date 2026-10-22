"""Read-only Jev buyer-demand shortlist against existing Buyer Scout.

External source posts remain hypotheses, not confirmed buyers, contracts or
automatic outreach tasks. No ingestion of contact data or email transport.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_explicit_buyer_source_triage import review_direct_buyer_requests

ROOT=Path("/srv/empire_os")
SOURCE=Path("docs/commercial/JEV_DIRECT_B2B_BUYER_REQUEST_SOURCES_20261022.json")
BUYER=ROOT/"runtime/buyer_capacity_readiness/latest.json"
OUTPUT=Path("docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json")


def _bounded(path:Path,max_size:int)->dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=max_size:
        raise ValueError("pinned original source unavailable")
    obj=json.loads(path.read_text("utf8"))
    if not isinstance(obj,dict):
        raise ValueError("expected bounded public source document")
    return obj


def current_review(*,now:datetime)->dict:
    repo=Path(__file__).resolve().parents[1]
    original=repo/SOURCE
    source=_bounded(original,25000)
    buyer=_bounded(BUYER,100000)
    result=review_direct_buyer_requests(source,as_of=now,buyer_capacity=buyer)
    if (result["distinct_public_purchase_need_posts"]!=5
        or result["verified_business_buyers"]!=0
        or result["officially_awarded_business_orders"]!=0
        or result["live_bids_submitted"]!=0
        or result["outbound_sent"]!=0
        or result["crm_writes"] is not False):
        raise ValueError("no unreviewed commercial authority from a source post")
    result["pinned_external_source_sha256"]=sha256(original.read_bytes()).hexdigest()
    result["buyer_capacity_snapshot_sha256"]=sha256(BUYER.read_bytes()).hexdigest()
    result["audit_at_utc"]=now.astimezone(timezone.utc).isoformat()
    result["public_marketplace_listing_date_original_exact_timestamp_unverified"]=True
    result["original_platform_account_is_not_legal_buyer_identity"]=True
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    dest=root/OUTPUT
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("refuse replacement of original demand evidence receipt")
    out=current_review(now=datetime.now(timezone.utc))
    with dest.open("x",encoding="utf8") as f:
        json.dump(out,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":out["status"],
        "public_demand_requests":out["distinct_public_purchase_need_posts"],
        "buyer_scout":out["buyer_capacity_aggregate_status"],
        "legal_buyers_verified":out["verified_business_buyers"],
        "orders_awarded":out["officially_awarded_business_orders"],
        "outbound":out["outbound_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
