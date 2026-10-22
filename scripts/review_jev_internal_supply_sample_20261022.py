"""Run a privacy-safe synthetic website QA canary for a proposed US B2B offer."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_internal_b2b_sample_qa import review_internal_business_sample

SAMPLE=Path("docs/commercial/JEV_WEB_AGENCY_SYNTHETIC_SUPPLY_SAMPLE_20261022.json")
PRIOR=Path("docs/commercial/JEV_PUBLIC_TWO_CASE_PREOFFER_REVIEW_20261022.json")
OUTPUT=Path("docs/commercial/JEV_WEB_AGENCY_SYNTHETIC_QA_CANARY_20261022.json")


def run_qa()->dict:
    root=Path(__file__).resolve().parents[1]
    paths=(root/SAMPLE,root/PRIOR)
    if any(p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=40000 for p in paths):
        raise ValueError("pinned bounded aggregate input unavailable")
    sample=json.loads(paths[0].read_text())
    parent=json.loads(paths[1].read_text())
    if (parent.get("schema_version")!="empire.jev.public_b2b_preoffer_review.v1"
        or parent.get("status")!="B2B_PREOFFER_READINESS_HELD_RESEARCH_ONLY"
        or parent.get("lead_supply_counts",{}).get("sellable")!=0
        or parent.get("commercial_offers_ready")!=0
        or parent.get("promised_deliveries")!=0
        or parent.get("messages_sent")!=0
        or parent.get("database_writes") is not False
        or parent.get("execution_authority")!="none"):
        raise ValueError("unverified commercial parent or unapproved fulfillment")
    receipt=review_internal_business_sample(sample)
    receipt["synthetic_fixture_sha256"]=sha256(paths[0].read_bytes()).hexdigest()
    receipt["pinned_read_only_preoffer_sha256"]=sha256(paths[1].read_bytes()).hexdigest()
    receipt["real_pilot_source_rights_cleared"]=False
    receipt["original_website_fetches_performed"]=0
    receipt["recipient_names_or_contacts_collected"]=0
    return receipt


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args()
    output=Path(__file__).resolve().parents[1]/OUTPUT
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("cannot replace original synthetic review")
    receipt=run_qa()
    with output.open("x",encoding="utf8") as f:
        json.dump(receipt,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status":receipt["status"],
        "fictional_rows":receipt["synthetic_records_checked"],
        "fictional_qa_passes":receipt["synthetic_qa_pattern_passes"],
        "real_accepted_leads":receipt["actual_available_accepted_records"],
        "outbound":receipt["outbound_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
