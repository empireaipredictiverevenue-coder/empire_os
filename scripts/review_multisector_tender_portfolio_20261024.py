"""On-demand, read-only original Tender Consultant multi-sector deal review."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.tender_multisector_qualification_20261024 import materialize

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--write-private",action="store_true",
                        help="Allow ONLY private 0600 reviewed research; never a DB/CRM/contact action")
    args=parser.parse_args()
    if not args.write_private:
        print(json.dumps({"status":"HELD_EXPLICIT_PRIVATE_REVIEW_REQUIRED",
                          "new_outreach_authorized":False,"bid_submitted":False},sort_keys=True))
        return 2
    r=materialize(Path(args.repo_root))
    print(json.dumps({
        "status":r["status"],
        "independently_grounded_public_opportunities":r["independent_opportunities_count"],
        "distinct_sectors":r["distinct_sectors_count"],
        "official_procurement_records_verified":r["public_procurement_cases_verified"],
        "innovator_challenge_pages_verified":r["innovation_challenge_pages_verified"],
        "read_only":True,
        "customer_orders":r["actual_clients_contracted"],
        "quotes_or_bids_authorized":False,
        "empiredb_writes":r["source_data_accepted_to_canonical_empiredb"],
        "new_emails_sent":r["new_emails_sent"],
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
