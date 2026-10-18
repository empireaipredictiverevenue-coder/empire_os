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
FULL_DAY_FILENAME="runtime/data_brokerage/nyc_dobnow_property_three_agency_full_day_latest.json"
FULL_DAY_SCHEMA="empire.permit_property_three_agency_full_day.v2"
STATES={
    "TRI_AGENCY_BIN_AND_LOT_MATCH",
    "TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH",
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
    base=Path(repo_root)
    full_day=base/FULL_DAY_FILENAME
    use_full=full_day.exists() or full_day.is_symlink()
    p=full_day if use_full else base/FILENAME
    max_size=1_000_000 if use_full else 150_000
    if not p.is_file():
        return missing
    if p.is_symlink() or p.stat().st_size>max_size:
        return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
    try:
        review=json.loads(p.read_text(encoding="utf-8"))
        expect_schema=FULL_DAY_SCHEMA if use_full else SCHEMA
        if (not isinstance(review,dict) or review.get("schema")!=expect_schema
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
                or count<1 or count>(1200 if use_full else 40)
                or count!=len(raw)):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        if use_full:
            # An unverified volume claim is not a complete date partition.
            if (review.get("coverage_state") !=
                    "FULL_ISSUED_DAY_OFFICIAL_COUNT_MATCH_AT_OBSERVATION"
                    or review.get("input_dob_sample_may_be_incomplete") is not False
                    or review.get("source_change_caveat") is None
                    or review.get("person_company_buyer_verified") is not False
                    or review.get("property_ownership_verified") is not False):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            rows=review.get("source_permit_row_count")
            before=review.get("official_day_count_before_scan")
            after=review.get("official_day_count_after_scan")
            pages=review.get("source_page_receipts")
            chunks=review.get("property_chunks")
            if (type(rows) is not int or not 0<=rows<=1200
                    or type(before) is not int or type(after) is not int
                    or rows!=before or before!=after
                    or not isinstance(pages,list) or not 1<=len(pages)<=30
                    or review.get("source_page_count")!=len(pages)
                    or sum((x.get("official_rows",-999) for x in pages
                            if isinstance(x,dict)),0)!=rows
                    or any(not isinstance(x,dict) or x.get("page")!=i
                           or not isinstance(x.get("two_dob_selected_response_sha256"),dict)
                           or not isinstance(x.get("two_dob_selected_response_sha256",{}).get("permits"),str)
                           for i,x in enumerate(pages))
                    or not isinstance(chunks,list) or not 1<=len(chunks)<=30
                    or review.get("property_review_chunk_count")!=len(chunks)
                    or sum((x.get("job_count",-999) for x in chunks
                            if isinstance(x,dict)),0)!=count
                    or any(not isinstance(x,dict) or x.get("chunk_index")!=i
                           or not 1<=x.get("job_count",0)<=40
                           or not isinstance(x.get("source_selected_response_receipts"),list)
                           or len(x["source_selected_response_receipts"])!=2
                           for i,x in enumerate(chunks))):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            day=review.get("issued_day")
            if (not isinstance(day,str) or
                    not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day)):
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
                    or (use_full and row.get("permit_original_issued_date")!=day)
                    or row.get("commercial_contact_authorized") is not False
                    or row.get("verified_business_buyer") is not False
                    or row.get("warehouse_operation_verified") is not False):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            if use_full:
                lot=row.get("permit_tax_lot_bbl")
                base_lot=row.get("footprint_base_bbl")
                billing_lot=row.get("footprint_mappluto_bbl")
                basis=row.get("reference_match_basis")
                if (not isinstance(lot,str) or not re.fullmatch(r"\d{10}",lot)
                        or basis not in ("BASE_PHYSICAL_LOT",
                                         "MAPPLUTO_BILLING_LOT","UNCONFIRMED")):
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
                if state=="TRI_AGENCY_BIN_AND_LOT_MATCH" and (
                    basis!="BASE_PHYSICAL_LOT" or base_lot!=lot
                    or billing_lot not in (None,lot)
                ):
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
                if state=="TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH" and (
                    basis!="MAPPLUTO_BILLING_LOT" or billing_lot!=lot
                    or base_lot==lot
                ):
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
                if state=="BUILDING_TAX_LOT_CONFLICT" and (
                    base_lot==lot and billing_lot in (None,lot)
                    or billing_lot==lot
                ):
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            jobs.add(job)
            statuses[state]+=1
            category=row.get("dcp_land_use_category")
            if not isinstance(category,str) or len(category)>40:
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
            use[category]+=1
            if row.get("industrial_tax_lot_context_corroborated") is True:
                if (state not in ("TRI_AGENCY_BIN_AND_LOT_MATCH",
                                  "TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH")
                        or category!="INDUSTRIAL_MANUFACTURING"):
                    return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
                industrial+=1
        if use_full:
            def distinct_pairs(records):
                return len({(r["permit_building_bin"],r["permit_tax_lot_bbl"])
                            for r in records})
            pairs={
                "all_permit_events_distinct_bin_bbl_pairs":distinct_pairs(raw),
                "corroborated_industrial_permit_events_distinct_bin_bbl_pairs":
                    distinct_pairs([r for r in raw
                                    if r["industrial_tax_lot_context_corroborated"] is True]),
                "unresolved_reference_mismatch_events_distinct_bin_bbl_pairs":
                    distinct_pairs([r for r in raw
                                    if r["building_tax_lot_evidence_state"] in (
                                        "BUILDING_TAX_LOT_CONFLICT",
                                        "DCP_BOROUGH_CONFLICT")]),
                "commercial_office_permit_events_distinct_bin_bbl_pairs":
                    distinct_pairs([r for r in raw
                                    if r["dcp_land_use_category"]=="COMMERCIAL_OFFICE"]),
            }
            if (review.get("reference_pair_basis")!=
                    "OFFICIAL_DOB_BIN_AND_DOB_BBL_NOT_INDEPENDENT_PROPERTY_IDENTITY"
                    or review.get("distinct_bin_bbl_reference_pair_counts")!=pairs):
                return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        if (dict(statuses)!=review.get("event_level_join_status_counts")
                or dict(use)!=review.get("event_level_landuse_category_counts")
                or industrial!=review.get("event_level_industrial_lot_context_count")):
            return {**missing,"status":"UNTRUSTED_REVIEW_FILE"}
        return {
            "status":("FULL_ISSUED_DAY_PROPERTY_REFERENCES_REVIEWED"
                      if use_full else "OFFICIAL_SOURCE_REFERENCES_REVIEWED"),
            "source_day_count_reconciled":use_full,
            "official_source_row_count":rows if use_full else None,
            "issued_day":day if use_full else None,
            "reviewed_at_utc":stamp.isoformat(),
            "reviewed_permit_event_count":count,
            "three_agency_bin_bbl_reference_match_count":
                (statuses["TRI_AGENCY_BIN_AND_LOT_MATCH"]
                 + statuses["TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH"]),
            "three_agency_billing_lot_reference_match_count":
                statuses["TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH"],
            "building_tax_lot_reference_conflict_count":
                statuses["BUILDING_TAX_LOT_CONFLICT"]+statuses["DCP_BOROUGH_CONFLICT"],
            "distinct_permit_bin_bbl_reference_pair_count":
                pairs["all_permit_events_distinct_bin_bbl_pairs"] if use_full else None,
            "distinct_industrial_bin_bbl_reference_pair_count":
                pairs["corroborated_industrial_permit_events_distinct_bin_bbl_pairs"]
                if use_full else None,
            "distinct_unresolved_bin_bbl_reference_pair_count":
                pairs["unresolved_reference_mismatch_events_distinct_bin_bbl_pairs"]
                if use_full else None,
            "distinct_commercial_office_bin_bbl_reference_pair_count":
                pairs["commercial_office_permit_events_distinct_bin_bbl_pairs"]
                if use_full else None,
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
