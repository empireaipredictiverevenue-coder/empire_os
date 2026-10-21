"""Read original 234MB PostgreSQL dump in bounded stream for Jev owner review.

No application DB credentials, database connection, private contact output,
record export, sends, external model inference, or database mutation.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re

from empire_os.jev_large_prospect_dump_reader import scan_prospect_copy_stream

ROOT=Path("/srv/empire_os")
DUMP=ROOT/"runtime/data_cloud/supabase_public_data.sql"
VERIFIED=ROOT/"runtime/data_cloud/shadow_independent_verify_latest.json"
COMPARED=ROOT/"runtime/data_cloud/dual_read_compare_latest.json"
OUTPUT="JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json"


def original_recovery_proof()->dict:
    if (VERIFIED.is_symlink() or COMPARED.is_symlink()
        or not VERIFIED.is_file() or not COMPARED.is_file()
        or VERIFIED.stat().st_size>100000
        or COMPARED.stat().st_size>100000):
        raise ValueError("original recovery verification unavailable")
    verified=json.loads(VERIFIED.read_text())
    compared=json.loads(COMPARED.read_text())
    if (verified.get("schema_version")!="empire.shadow-independent-verify.v1"
        or verified.get("verified") is not True
        or verified.get("read_only") is not True
        or verified.get("production_cutover_authority") is not False
        or compared.get("schema_version")!="empire.dual-read-compare.v1"
        or compared.get("all_equal") is not True
        or compared.get("read_only") is not True
        or compared.get("production_cutover_authority") is not False):
        raise ValueError("historical independently verified DB ID-set contract missing")
    a=[x for x in verified["tables"] if x.get("table")=="prospects"]
    b=[x for x in compared["tables"] if x.get("table")=="prospects"]
    if (len(a)!=1 or len(b)!=1 or b[0].get("equal") is not True
        or any(a[0].get(k)!=b[0].get(k) for k in (
            "source_rows","target_rows","source_pk_sha256","target_pk_sha256"))):
        raise ValueError("original two recovery verifiers disagree")
    return a[0]


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--receipt-tag",default=None,
                        help="new YYYYMMDDTHHMMSSZ receipt; never overwrite")
    args=parser.parse_args()
    name=OUTPUT
    if args.receipt_tag is not None:
        if not re.fullmatch(r"20\d{6}T[012]\d[0-5]\d[0-5]\dZ",args.receipt_tag):
            raise ValueError("unsafe or invalid exact new receipt tag")
        name="JEV_LARGE_PROSPECT_DUMP_STREAM_"+args.receipt_tag+".json"
    dest=Path(__file__).resolve().parents[1]/"docs/commercial"/name
    if (dest.exists() or dest.is_symlink() or not dest.parent.is_dir()):
        raise ValueError("refuse to replace an existing source proof")
    evidence=scan_prospect_copy_stream(DUMP,historical=original_recovery_proof())
    if (evidence["status"]!="HISTORIC_PROSPECT_COPY_IDENTITY_MATCH_REVIEW_ONLY"
        or evidence["historical_independent_id_set_match"] is not True
        or evidence["model_records_processed"]!=0
        or evidence["commercial_leads_authorized"]!=0
        or evidence["outreach_sent"]!=0
        or evidence["database_writes"] is not False):
        raise ValueError("unverified or unauthorised prospect export")
    evidence["observed_at_utc"]=datetime.now(timezone.utc).isoformat()
    with dest.open("x",encoding="utf-8") as f:
        json.dump(evidence,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":evidence["status"],
        "bytes":evidence["source_size_bytes"],
        "rows":evidence["source_counted_copy_rows"],
        "id_set_checksum_match":evidence["historical_independent_id_set_match"],
        "scan_ms":evidence["scan_elapsed_ms"],
        "niche_bucket_count":len(evidence["niche_aggregate_counts"]),
        "market_bucket_count":len(evidence["metro_aggregate_counts"]),
        "emails_exported":0,
        "model_records_processed":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
