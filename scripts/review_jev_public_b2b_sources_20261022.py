"""One-shot public-web original B2B request candidate triage.

Makes an owner-review receipt, not a contact list, prospect promotion,
Search Fabric server fetch claim, CRM task or outreach approval.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import argparse
import json
from pathlib import Path
from empire_os.jev_external_public_need_review import review_public_b2b_needs

SOURCE=Path("docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_CANDIDATES_20261022.json")
OUTPUT=Path("docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_REVIEW_20261022.json")


def run()->dict:
    root=Path(__file__).resolve().parents[1]
    path=root/SOURCE
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=50000:
        raise ValueError("bounded reviewed public source list required")
    raw=path.read_bytes()
    rows=json.loads(raw)
    result=review_public_b2b_needs(rows,as_of=date(2026,10,22))
    result["original_manual_public_web_review_source_sha256"]=sha256(raw).hexdigest()
    result["original_page_fetch_to_empireos_server_successful"]=False
    result["original_business_identity_or_rights_admitted"]=False
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=root/OUTPUT
    if target.is_symlink() or target.exists() or not target.parent.is_dir():
        raise ValueError("original reviewer receipt cannot be overwritten")
    result=run()
    with target.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],
        "public_original_web_candidates":result["original_source_pages_observed_in_web_review"],
        "direct_supplier_search_claims":result["direct_claims_of_provider_search"],
        "research_lanes":result["lanes"],
        "buyers_verified":result["verified_legal_business_buyers"],
        "crm_writes":result["crm_writes"],
        "outbound":result["approved_outbound_messages"],
    },sort_keys=True))


if __name__=="__main__":
    main()
