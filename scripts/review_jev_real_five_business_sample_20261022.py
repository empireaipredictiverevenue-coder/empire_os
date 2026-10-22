"""One-shot original business registry and first-party website QA packet.

No addresses, contacts, outreach, promotions, CRM/DB writes or bulk resale.
Website observations are pinned to avoid refetching HTTP 429 sources.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_real_business_five_sample import review_five_businesses

SOURCE = Path("docs/commercial/JEV_REAL_FIVE_BUSINESS_SITE_OBSERVATIONS_20261022.json")
OUTPUT = Path("docs/commercial/JEV_REAL_FIVE_BUSINESS_QA_RECEIPT_20261022.json")


def review_once(*,now:datetime)->dict:
    repo=Path(__file__).resolve().parents[1]
    packet=repo/SOURCE
    if (packet.is_symlink() or not packet.is_file()
        or not 0<packet.stat().st_size<=10000):
        raise ValueError("fixed bounded first-party website observation missing")
    raw=packet.read_bytes()
    web_evidence=json.loads(raw)
    report=review_five_businesses(
        now=now,live_web_checks=False,observed_web=web_evidence)
    if (report["unique_selected_businesses"]!=5
        or report["official_registry_location_rows_seen"]!=7
        or report["actual_no_website_leads_verified"]!=0
        or report["buyer_purchase_intent_verified"]!=0
        or report["customer_accepted_leads"]!=0
        or report["crm_writes"] is not False
        or report["outbound_sent"]!=0
        or report["database_writes"] is not False
        or report["execution_authority"]!="none"):
        raise ValueError("real research cannot become commercial lead delivery")
    report["pinned_first_party_site_observations_sha256"]=sha256(raw).hexdigest()
    report["no_marketing_data_or_person_contact_fields_requested"]=True
    report["current_industry_classification_independently_proven"]=False
    report["registry_row_does_not_prove_current_contracting_license"]=True
    report["sales_ready_customer_records"]=0
    return report


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    dest=repo/OUTPUT
    if dest.is_symlink() or dest.exists() or not dest.parent.is_dir():
        raise ValueError("cannot overwrite original real-business research receipt")
    result=review_once(now=datetime.now(timezone.utc))
    with dest.open("x",encoding="utf-8") as output:
        json.dump(result,output,sort_keys=True,indent=2)
        output.write("\n")
    print(json.dumps({
        "status":result["status"],
        "businesses":result["unique_selected_businesses"],
        "location_rows":result["official_registry_location_rows_seen"],
        "first_party_sites_confirmed_200":result["first_party_sites_directly_confirmed"],
        "real_missing_website_proven":result["actual_no_website_leads_verified"],
        "verified_buyers":result["buyer_purchase_intent_verified"],
        "outbound":result["outbound_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
