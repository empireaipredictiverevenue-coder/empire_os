"""Join original Jev sector priorities with current public client-pain evidence.

Public contractor bids are DISCOVERY CANDIDATES for contractor WORK, never
evidence that a contractor wants to purchase Empire AI leads or SaaS.
No source scraping, login, model calls, CRM writes, Department dispatch,
mail or use of archived personal details.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from empire_os.jev_client_pain_discovery import (
    discover_client_pains, observations_from_existing_canonical_inbox,
)
from empire_os.jev_top_sector_demand_gap import review_sector_demand_gap, WORK_TYPE

ROOT=Path("/srv/empire_os")
HISTORY=ROOT/"runtime/community_intent/observations.json"
INBOX=ROOT/"runtime/acquisition/signal_inbox.json"
MAX_PUBLIC_BYTES=12_000_000
OWN=Path("docs/commercial/JEV_SECTOR_RESEARCH_PRIORITY_20261022.json")
OUTPUT=Path("docs/commercial/JEV_TOP_SECTOR_CLIENT_DEMAND_GAP_20261022.json")

# Discovered on SAM.gov; the original notices were *not* independently
# extracted from the agency's JS-rendered page. We only retain notice IDs
# and sector types for owner checks; no contacts, bid amounts or lead claims.
PUBLIC_CONTRACTOR_BID_DISCOVERY=(
    {"notice_id":"W9127826RA089","sector":"general_contractor",
     "opportunity_type":WORK_TYPE,
     "source_original_notice_independently_inspected":False,
     "contractor_bids_are_not_empire_saas_buyers":True,
     "customer_outreach_authorized":False},
    {"notice_id":"36C25727Q0022","sector":"roofing",
     "opportunity_type":WORK_TYPE,
     "source_original_notice_independently_inspected":False,
     "contractor_bids_are_not_empire_saas_buyers":True,
     "customer_outreach_authorized":False},
    {"notice_id":"140L4326Q0127","sector":"hvac",
     "opportunity_type":WORK_TYPE,
     "source_original_notice_independently_inspected":False,
     "contractor_bids_are_not_empire_saas_buyers":True,
     "customer_outreach_authorized":False},
)


def _read_source(file:Path, maximum:int)->dict[str,Any]:
    if (file.is_symlink() or not file.is_file()
        or not 0<file.stat().st_size<=maximum):
        raise ValueError("invalid bounded original source path")
    item=json.loads(file.read_text("utf8"))
    if not isinstance(item,dict):
        raise ValueError("original source must be a canonical dictionary")
    return item


def run_demand_gap(*, now:datetime)->dict[str,Any]:
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware audit clock required")
    repo=Path(__file__).resolve().parents[1]
    sector_receipt=_read_source(repo/OWN,200000)
    history=_read_source(HISTORY,MAX_PUBLIC_BYTES)
    inbox=_read_source(INBOX,MAX_PUBLIC_BYTES)
    if not isinstance(history.get("observations"),list):
        raise ValueError("original community history missing")
    community=history["observations"]
    inbound=observations_from_existing_canonical_inbox(inbox)
    if len(community)+len(inbound)>500:
        raise ValueError("unbounded actual client pain observation volume")
    summary=discover_client_pains([*community,*inbound],now=now,
                                  include_private_source_links=False)
    review=review_sector_demand_gap(
        sector_receipt,summary,
        public_procurement_candidates=PUBLIC_CONTRACTOR_BID_DISCOVERY)
    review["audited_at_utc"]=now.astimezone(timezone.utc).isoformat()
    review["sector_priority_original_receipt_sha256"]=sha256(
        (repo/OWN).read_bytes()).hexdigest()
    review["history_observations_checked"]=len(community)
    review["current_canonical_social_signals_checked"]=len(inbound)
    review["original_social_post_publication_date_verified"]=False
    review["reviewed_original_notice_body_hashes"]=0
    return review


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    destination=root/OUTPUT
    if destination.is_symlink() or destination.exists():
        raise ValueError("original gap receipt exists; cannot overwrite")
    result=run_demand_gap(now=datetime.now(timezone.utc))
    with destination.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],
        "community_history":result["history_observations_checked"],
        "canonical_social":result["current_canonical_social_signals_checked"],
        "classified_pain_topics":result["public_pain_or_topic_observations"],
        "per_sector_candidates":{
            x["sector"]:x["unverified_public_pain_review_candidates"]
            for x in result["sector_demand_research"]},
        "public_bid_discovery_only":len(result["contractor_work_procurement_discovery_candidates"]),
        "verified_buyers":result["software_or_marketing_clients_verified"],
        "outreach":result["outbound_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
