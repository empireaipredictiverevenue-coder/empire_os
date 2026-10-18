"""Fail-closed reader for traceable, limited official property claim receipts.

This is a source/claim-kind guard, not proof of external publisher authorship.
Rejects any larger commercial inference, and never exports individual records.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json,re

SCHEMA="empire.property_claim_evidence.v1"
PATH="runtime/data_brokerage/nyc_property_four_pair_claims_latest.json"
MANIFEST="runtime/data_brokerage/nyc_property_four_pair_claims_latest.provenance.json"
ALLOWED_SOURCE_CLAIMS={
    "DOB_ISSUED_PERMIT_EVENT",
    "OTI_PLUTO_TAXLOT_REFERENCE_MATCH",
    "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",
    "PLUTO_PUBLISHED_STORAGE_AREA_VALUE",
    "OTI_BBL_CONFLICT_RECORDED",
    "DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",
}
EXPECTED_DATASETS={"NYC_DOB_NOW_PERMITS":"rbx6-tga4",
                   "NYC_OTI_BUILDINGS":"5zhs-2jue",
                   "NYC_DCP_PLUTO":"64uk-42ks",
                   "NYC_DOB_NOW_COO":"pkdm-hqz6"}
SRC_RECEIPTS={
    "OTI_BIN_BASE_MAPPLUTO":"5zhs-2jue",
    "DCP_PLUTO_LOT_CLASS_AND_AREA":"64uk-42ks",
    "DOB_NOW_COO_STATUS_FOR_SELECTED_BIN":"pkdm-hqz6",
    "DOB_PERMIT_SOURCE":"rbx6-tga4",
}
HEX=re.compile(r"[0-9a-f]{64}\Z")


def _read(repo_root:Path):
    p=Path(repo_root)/PATH;m=Path(repo_root)/MANIFEST
    if not p.is_file() or not m.is_file() or p.is_symlink() or m.is_symlink():
        return None
    if p.stat().st_size>80_000 or m.stat().st_size>5_000:
        return None
    body=p.read_bytes()
    data=json.loads(body)
    proof=json.loads(m.read_text())
    digest=sha256(body).hexdigest()
    if (proof.get("derived_evidence_sha256")!=digest
            or proof.get("schema")!="empire.property_claim_evidence_receipt.v1"
            or proof.get("consumer_sales_release_authorized") is not False):
        return None
    return data


def validated_claims(repo_root:Path,*,now:datetime | None=None):
    try:
        d=_read(Path(repo_root))
        if (not isinstance(d,dict) or d.get("schema")!=SCHEMA
                or d.get("mode")!="OBSERVE" or d.get("execution_authority")!="none"
                or d.get("bounded_pair_count")!=4
                or d.get("source_full_day_issued_date")!="2026-10-16"
                or not isinstance(d.get("source_full_day_report_sha256"),str)
                or not HEX.fullmatch(d["source_full_day_report_sha256"])
                or d.get("source_datasets")!=EXPECTED_DATASETS
                or d.get("external_distribution_authorized") is not False
                or d.get("warehouse_operations_verified_count")!=0
                or d.get("ownership_or_buyer_verified_count")!=0):
            return None
        t=datetime.fromisoformat(d["observed_at_utc"].replace("Z","+00:00"))
        at=now or datetime.now(timezone.utc)
        if t.utcoffset() is None or at.utcoffset() is None:
            return None
        delta=at.astimezone(timezone.utc)-t.astimezone(timezone.utc)
        if not -timedelta(minutes=5)<=delta<=timedelta(hours=48):
            return None
        receipts=d.get("live_source_selected_response_receipts")
        if (not isinstance(receipts,list) or len(receipts)!=3
                or {r.get("official_dataset_id") for r in receipts
                    if isinstance(r,dict)}!={"64uk-42ks","5zhs-2jue","pkdm-hqz6"}
                or any(not isinstance(r,dict) or
                       not HEX.fullmatch(str(r.get("selected_response_sha256")))
                       or not 0<=r.get("observed_source_rows",-1)<100
                       for r in receipts)):
            return None
        claims=d.get("claim_reviews")
        if not isinstance(claims,list) or len(claims)!=4:
            return None
        pair_keys=set()
        classes=Counter()
        for c in claims:
            if not isinstance(c,dict):
                return None
            refs=c.get("entity_reference")
            if (not isinstance(refs,dict)
                    or not re.fullmatch(r"[1-5]\d{6}",str(refs.get("bin","")))
                    or not re.fullmatch(r"\d{10}",str(refs.get("dob_bbl","")))):
                return None
            key=(refs["bin"],refs["dob_bbl"])
            if key in pair_keys:return None
            pair_keys.add(key)
            state=c.get("evidence_grade")
            if state not in {
                "THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS",
                "DOB_REFERENCE_CORROBORATED_OTI_CONFLICT_REMAINS",
                "REFERENCE_CONFLICT_UNRESOLVED",
            }:return None
            statements=c.get("allowed_evidence_statements")
            if not isinstance(statements,list) or not set(statements)<=ALLOWED_SOURCE_CLAIMS:
                return None
            if "DOB_ISSUED_PERMIT_EVENT" not in statements:
                return None
            supporting=c.get("evidence_receipts")
            if (not isinstance(supporting,list) or len(supporting)!=4
                    or {r.get("fact") for r in supporting
                        if isinstance(r,dict)}!=set(SRC_RECEIPTS)
                    or any(not isinstance(r,dict)
                           or r.get("source_dataset_id")!=SRC_RECEIPTS.get(r.get("fact"))
                           for r in supporting)):
                return None
            source_digests={r["official_dataset_id"]:r["selected_response_sha256"]
                            for r in receipts}
            for record in supporting:
                if record["fact"]=="DOB_PERMIT_SOURCE":
                    if record.get("local_full_day_report_sha256")!=d["source_full_day_report_sha256"]:
                        return None
                elif record.get("selected_source_response_sha256")!=source_digests[record["source_dataset_id"]]:
                    return None
            if (c.get("customer_claim_approved") is not False
                    or c.get("outbound_authorized") is not False
                    or not isinstance(c.get("not_proven"),list)
                    or "ACTIVE_WAREHOUSE_OPERATIONS" not in c["not_proven"]
                    or "NAMED_SITE_OWNER_OR_OPERATOR" not in c["not_proven"]):
                return None
            if state=="THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS":
                if (c.get("source_dof_building_class_as_reported") not in ("E2","E9")
                        or c.get("source_dof_building_class_label") not in (
                            "CONTRACTORS_WAREHOUSE_BUILDING_CLASS",
                            "MISCELLANEOUS_WAREHOUSE_BUILDING_CLASS"
                        ) or
                        "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS" not in statements):
                    return None
            else:
                if "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS" in statements:
                    return None
            classes[state]+=1
        if (classes["THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS"]!=2
                or sum(classes.values())!=4):
            return None
        return d
    except (OSError,ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
        return None


def supported_claim(repo_root:Path,*,bin_id:str,dob_bbl:str,
                    statement:str,now:datetime | None=None)->bool:
    """No inference: only a stated field kind with four official receipts."""
    data=validated_claims(repo_root,now=now)
    if data is None or statement not in ALLOWED_SOURCE_CLAIMS:
        return False
    return any(
        r["entity_reference"]["bin"]==bin_id
        and r["entity_reference"]["dob_bbl"]==dob_bbl
        and statement in r["allowed_evidence_statements"]
        for r in data["claim_reviews"]
    )


def property_claims_summary(repo_root:Path,*,now:datetime | None=None):
    data=validated_claims(repo_root,now=now)
    base={"status":"NO_VERIFIED_PROPERTY_CLAIM_RECEIPTS",
          "external_claims_authorized":False,
          "active_warehouse_businesses_verified":0,
          "execution_authority":"none"}
    if data is None:return base
    return {**base,"status":"FOUR_SOURCE_BOUND_REFERENCE_CLAIMS_REVIEWED",
            "as_observed_at_utc":data["observed_at_utc"],
            "source_report_sha256":data["source_full_day_report_sha256"],
            "bounded_reference_pair_count":4,
            "official_warehouse_class_reference_pairs":2,
            "unresolved_lot_reference_pairs":2,
            "permit_jobs_in_four_pairs":sum(x["permit_events_observed"]
                                          for x in data["claim_reviews"]),
            "source_receipts_validated":True}
