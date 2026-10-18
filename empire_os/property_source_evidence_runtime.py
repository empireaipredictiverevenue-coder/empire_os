"""Existing Property Intelligence's optional read-only three-agency source review.

An observation of an official permit/property *reference* is not an
independently verified canonical property, asset owner, buyer or active
warehouse. No network or database calls in this read-model.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,re

SCHEMA="empire.permit_property_three_agency_evidence.v1"
FILENAME="runtime/data_brokerage/nyc_dobnow_property_three_agency_latest.json"
STATES={
    "TRI_AGENCY_BIN_AND_LOT_MATCH",
    "BUILDING_TAX_LOT_CONFLICT",
    "DCP_LOT_ONLY_BIN_UNCONFIRMED",
    "OTI_BIN_ONLY_TAX_LOT_UNCONFIRMED",
    "DCP_BOROUGH_CONFLICT",
    "AMBIGUOUS_SOURCE_IDENTITY",
    "PROPERTY_SOURCE_REFERENCE_UNMATCHED",
}
SRC={"dob_now_filings":"w9ak-ipjd",
     "dob_now_initial_permits":"rbx6-tga4",
     "oti_building_footprints":"5zhs-2jue",
     "dcp_pluto":"64uk-42ks"}


def load_property_reference_summary(repo_root: Path, *, now=None) -> dict:
    """Validate a small local research receipt, never add to customer records."""
    missing={"status":"NO_REVIEW_FILE",
             "source_reference_only":True,
             "verified_property_opportunity_count":None,
             "warehouse_operation_verified_count":0,
             "execution_authority":"none"}
    p=Path(repo_root)/FILENAME
    if not p.is_file() or p.is_symlink() or p.stat().st_size>150_000:
        return missing
    try:
        review=json.loads(p.read_text(encoding="utf-8"))
        if (not isinstance(review,dict) or review.get("schema")!=SCHEMA
                or review.get("mode")!="OBSERVE"
                or review.get("execution_authority")!="none"
                or review.get("source_datasets")!=SRC
                or review.get("external_outreach_sent") is not False
                or review.get("data_warehouse_or_empiredb_mutated") is not False
                or review.get("rights_review_required_for_customer_distribution") is not True):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        raw=review.get("diagnostics")
        count=review.get("permit_event_count")
        if (not isinstance(raw,list) or type(count) is not int
                or count<1 or count>40 or count!=len(raw)):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        stamp=datetime.fromisoformat(review["reviewed_at_utc"].replace("Z","+00:00"))
        clock=now or datetime.now(timezone.utc)
        if stamp.utcoffset() is None or clock.utcoffset() is None:
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        age=clock.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)
        if age<-timedelta(minutes=5):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        if age>timedelta(hours=48):
            return {**missing,"status":"STALE_SOURCE_REVIEW"}
        statuses=Counter()
        jobs=set()
        use=Counter()
        industrial=0
        for row in raw:
            if not isinstance(row,dict):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            job=row.get("permit_job_filing_ref")
            state=row.get("building_tax_lot_evidence_state")
            if (not isinstance(job,str) or not re.fullmatch(r"[BMQSX]\d{8}-[A-Z]\d{1,2}",job)
                    or job in jobs or state not in STATES
                    or row.get("commercial_contact_authorized") is not False
                    or row.get("verified_business_buyer") is not False
                    or row.get("warehouse_operation_verified") is not False):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            jobs.add(job)
            statuses[state]+=1
            category=row.get("dcp_land_use_category")
            if not isinstance(category,str) or len(category)>40:
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            use[category]+=1
            if row.get("industrial_tax_lot_context_corroborated") is True:
                if state!="TRI_AGENCY_BIN_AND_LOT_MATCH" or category!="INDUSTRIAL_MANUFACTURING":
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
                industrial+=1
        if (dict(statuses)!=review.get("event_level_join_status_counts")
                or dict(use)!=review.get("event_level_landuse_category_counts")
                or industrial!=review.get("event_level_industrial_lot_context_count")):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        return {
            "status":"OFFICIAL_SOURCE_REFERENCES_REVIEWED",
            "reviewed_at_utc":stamp.isoformat(),
            "reviewed_permit_event_count":count,
            "three_agency_bin_bbl_reference_match_count":
                statuses["TRI_AGENCY_BIN_AND_LOT_MATCH"],
            "building_tax_lot_reference_conflict_count":
                statuses["BUILDING_TAX_LOT_CONFLICT"]+statuses["DCP_BOROUGH_CONFLICT"],
            "tax_lot_only_unconfirmed_building_count":
                statuses["DCP_LOT_ONLY_BIN_UNCONFIRMED"],
            "commercial_office_tax_lot_context_count":use["COMMERCIAL_OFFICE"],
            "industrial_manufacturing_tax_lot_context_count":industrial,
            "unknown_tax_lot_landuse_count":use["UNKNOWN"],
            "source_reference_only":True,
            "source_sample_incomplete":review.get("input_dob_sample_may_be_incomplete") is True,
            "verified_property_opportunity_count":None,
            "warehouse_operation_verified_count":0,
            "building_owner_or_buyer_verified":False,
            "source_agencies":["NYC DOB","NYC OTI","NYC DCP"],
            "execution_authority":"none",
        }
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
