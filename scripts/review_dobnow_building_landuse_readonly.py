#!/usr/bin/env python3
"""Explicit founder-directed NYC DOB NOW -> OTI footprints -> DCP PLUTO review.

Default only prints sanitized summary. --record-private updates one existing
internal research snapshot and original-derived evidence receipt, mode 0600.
No prospect ingestion, EmpireDB, email, paid API or new timer.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,os,tempfile

from empire_os.lead_sources.nyc_dobnow import current_event_sample
from empire_os.permit_property_source_join import review_official_building_landuse
from empire_os.property_source_evidence_runtime import FILENAME,load_property_reference_summary

ROOT=Path("/srv/empire_os")


def _private_atomic(path: Path, data: bytes) -> None:
    if path.is_symlink() or len(data)>150_000:
        raise ValueError("UNSAFE_INTERNAL_EVIDENCE_TARGET")
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".property_source_review.",suffix=".tmp",
                            dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as writer:
            os.fchmod(writer.fileno(),0o600)
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(*, repo_root: Path=ROOT, record_private: bool=False) -> dict:
    repo_root=Path(repo_root).resolve()
    source=current_event_sample()
    events=source["events"]
    if not events:
        raise ValueError("NO_RECENT_TWO_DOB_DATASET_EVENTS")
    report=review_official_building_landuse(events)
    report["input_dob_source_selected_response_sha256"]=source["source_response_sha256"]
    report["input_dob_sample_may_be_incomplete"]=source["sample_may_be_incomplete"]
    report["input_dob_raw_permit_rows"]=source["query_rows"]
    report["original_founder_directed_ai_assisted"]=True
    report["source_rights_not_granted_by_derived_evidence"]=True
    report["customer_facing_distributable"]=False
    encoded=(json.dumps(report,sort_keys=True,indent=2)+"\n").encode("utf-8")
    digest=sha256(encoded).hexdigest()
    summary={
        "status":"LIVE_OFFICIAL_BUILDING_TAXLOT_SOURCE_REVIEW",
        "input_dob_event_count":len(events),
        "raw_dob_permit_rows":source["query_rows"],
        "partial_dob_input":source["sample_may_be_incomplete"],
        "join_states":report["event_level_join_status_counts"],
        "landuse":report["event_level_landuse_category_counts"],
        "industrial_lot_context":report["event_level_industrial_lot_context_count"],
        "derived_evidence_sha256":digest,
        "private_record_written":False,
        "empiredb_or_canonical_signal_inbox_written":False,
        "outbound_or_payments":False,
    }
    if record_private:
        target=repo_root/FILENAME
        receipt=target.with_name(target.stem+".provenance.json")
        if target.is_symlink() or receipt.is_symlink():
            raise ValueError("UNSAFE_PRIVATE_RESEARCH_PATH")
        _private_atomic(target,encoded)
        manifest={
            "schema":"empire.original_derived_three_agency_receipt.v1",
            "captured_at_utc":datetime.now(timezone.utc).isoformat(),
            "derived_evidence_sha256":digest,
            "source_agencies":["NYC DOB","NYC OTI","NYC DCP"],
            "original_source_sha256":[
                *source["source_response_sha256"].values(),
                *[x["selected_response_sha256"]
                  for x in report["source_selected_response_receipts"]]
            ],
            "basis":"derived selected nonpersonal fields only",
            "source_rights_review_required":True,
            "no_buyer_or_property_owner_verified":True,
            "no_commercial_authority":True,
        }
        _private_atomic(receipt,(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode())
        assert sha256(target.read_bytes()).hexdigest()==digest
        projection=load_property_reference_summary(repo_root)
        if projection.get("status")!="OFFICIAL_SOURCE_REFERENCES_REVIEWED":
            raise ValueError("PROPERTY_RUNTIME_REJECTED_EVIDENCE_AFTER_WRITE")
        summary["private_record_written"]=True
        summary["property_read_model_status"]=projection["status"]
        summary["file_mode"]=oct(target.stat().st_mode&0o777)
    return summary


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--record-private",action="store_true")
    args=parser.parse_args()
    print(json.dumps(run(record_private=args.record_private),sort_keys=True))
