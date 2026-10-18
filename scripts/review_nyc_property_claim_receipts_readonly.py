#!/usr/bin/env python3
"""On-demand verification, no scheduled collection, CRM or communications.

Default reads and prints source-limited summary. --record-private writes only
the bounded research evidence and private provenance to existing runtime/
data_brokerage, never EmpireDB or any prospect/contact route.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import argparse,json,os,tempfile

from empire_os.property_claim_evidence_review import review_property_claims
from empire_os.property_claim_receipt_runtime import (
    PATH,MANIFEST,property_claims_summary,
)


def _atomic(path,data):
    if path.is_symlink() or len(data)>80_000:
        raise ValueError("UNSAFE_CLAIM_RECEIPT_PATH")
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".property_claim.",suffix=".tmp")
    try:
        with os.fdopen(fd,"wb") as writer:
            os.fchmod(writer.fileno(),0o600)
            writer.write(data);writer.flush();os.fsync(writer.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def run(*,repo_root=Path("/srv/empire_os"),record_private=False):
    repo_root=Path(repo_root).resolve()
    data=review_property_claims(repo_root=repo_root)
    encoded=(json.dumps(data,sort_keys=True,indent=2)+"\n").encode()
    digest=sha256(encoded).hexdigest()
    out={"status":"OFFICIAL_SELECTED_SOURCE_CLAIM_REVIEW",
         "pair_count":data["bounded_pair_count"],
         "underlying_source_report_sha256":data["source_full_day_report_sha256"],
         "evidence_sha256":digest,
         "claim_levels":[
             {"bin":x["entity_reference"]["bin"],
              "dob_bbl":x["entity_reference"]["dob_bbl"],
              "evidence_grade":x["evidence_grade"],
              "permit_jobs":x["permit_events_observed"],
              "issued_coo_selected_dataset_rows":x["coo_issued_records_matching_same_bin_bbl"]}
             for x in data["claim_reviews"]],
         "realised_revenue_verified":False,
         "warehouse_operator_verified":False,
         "customer_distribution_authorized":False,
         "private_receipt_written":False}
    if record_private:
        payload=repo_root/PATH; manifest=repo_root/MANIFEST
        if payload.is_symlink() or manifest.is_symlink():
            raise ValueError("UNSAFE_PRIVATE_CLAIM_DESTINATION")
        _atomic(payload,encoded)
        _atomic(manifest,(json.dumps({
            "schema":"empire.property_claim_evidence_receipt.v1",
            "derived_evidence_sha256":digest,
            "source_full_day_report_sha256":data["source_full_day_report_sha256"],
            "created_at_utc":datetime.now(timezone.utc).isoformat(),
            "consumer_sales_release_authorized":False,
            "source_rights_review_required":True,
            "source_responses_are_digest_not_signed_at_source":True,
        },sort_keys=True,indent=2)+"\n").encode())
        observed=property_claims_summary(repo_root)
        if observed["status"]!="FOUR_SOURCE_BOUND_REFERENCE_CLAIMS_REVIEWED":
            raise ValueError("CLAIMS_READER_REJECTED_CAPTURE")
        out["private_receipt_written"]=True
        out["private_reader_status"]=observed["status"]
    return out


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--record-private",action="store_true")
    args=parser.parse_args()
    print(json.dumps(run(record_private=args.record_private),sort_keys=True))
