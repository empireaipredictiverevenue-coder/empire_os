"""One-shot official SAM.gov public field review of three contractor tenders.

A manually checked public listing is not a continuously connected SAM API,
signed original document package, verified supplier or lead-gen buyer.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_sam_procurement_review import reconcile_official_work_notices
from scripts.review_jev_top_sector_demand_gap_20261022 import PUBLIC_CONTRACTOR_BID_DISCOVERY

FILE=Path("config/jev_sam_procurement_public_review_20261022.json")
OUTPUT=Path("docs/commercial/JEV_SAM_OFFICIAL_NOTICE_TRIAGE_20261022.json")


def review_verified_fields(*,now:datetime)->dict:
    repo=Path(__file__).resolve().parents[1]
    candidate=repo/FILE
    if candidate.is_symlink() or not candidate.is_file() or not 0<candidate.stat().st_size<=15000:
        raise ValueError("no fixed public SAM.gov field ledger")
    original=candidate.read_bytes()
    evidence=json.loads(original)
    expected={(r["notice_id"],r["sector"]) for r in PUBLIC_CONTRACTOR_BID_DISCOVERY}
    actual={(r["notice_id"],r["sector"]) for r in evidence["opportunities"]}
    if expected!=actual:
        raise ValueError("historical Research shortlist differs from official source review")
    result=reconcile_official_work_notices(evidence,now=now)
    result["curated_official_public_field_ledger_sha256"]=sha256(original).hexdigest()
    result["historical_research_discovery_shortlist_crosschecked"]=True
    result["current_sam_api_or_attachment_query_performed"]=False
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    destination=repo/OUTPUT
    if destination.is_symlink() or destination.exists() or not destination.parent.is_dir():
        raise ValueError("original official notice review receipt already exists")
    result=review_verified_fields(now=datetime.now(timezone.utc))
    with destination.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],
        "notice_count":result["notice_count"],
        "deadline_watch":result["deadline_watch_counts"],
        "verified_leadgen_buyers":result["direct_empire_saas_buying_requests_verified"],
        "outreach":result["automatic_outbound_allowed"],
        "live_sam_api_queried":result["current_sam_api_or_attachment_query_performed"],
        "execution_authority":result["execution_authority"],
    },sort_keys=True))


if __name__=="__main__":
    main()
