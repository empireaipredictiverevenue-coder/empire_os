"""Official-source claim contract for four specific NYC property references.

A claim must identify the precise source dataset/field, observed response
digest, publication context and explicit unproved higher-level hypotheses.
This is a bounded OBSERVE research reader; NO CRM, EmpireDB, email or timer.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json
import re

import requests

SCHEMA="empire.property_claim_evidence.v1"
PREVIOUS_SCHEMA="empire.permit_property_three_agency_full_day.v2"
COO_ID="pkdm-hqz6"
PLUTO_ID="64uk-42ks"
OTI_ID="5zhs-2jue"
COO_URL=f"https://data.cityofnewyork.us/resource/{COO_ID}.json"
PLUTO_URL=f"https://data.cityofnewyork.us/resource/{PLUTO_ID}.json"
OTI_URL=f"https://data.cityofnewyork.us/resource/{OTI_ID}.json"
DOF_CLASSES="https://www.nyc.gov/assets/finance/jump/hlpbldgcode.html"
MAX_SOURCE_ROWS=100
MAX_RESPONSE_BYTES=120_000
ALLOWED_PAIR_STATES={
    "INDUSTRIAL_CONTEXT_CORROBORATED",
    "DOB_OTI_BBL_UNRESOLVED",
}
CLASS_LABELS={
    "E2":"CONTRACTORS_WAREHOUSE_BUILDING_CLASS",
    "E9":"MISCELLANEOUS_WAREHOUSE_BUILDING_CLASS",
}
REPORT_REL="runtime/data_brokerage/nyc_dobnow_property_three_agency_full_day_latest.json"


def _bbl(value):
    try:
        if isinstance(value,bool) or not isinstance(value,(str,int)):
            return None
        n=Decimal(str(value))
        if not n.is_finite() or n!=n.to_integral_value():
            return None
        s=str(int(n))
        return s if re.fullmatch(r"\d{10}",s) else None
    except (ValueError,InvalidOperation):
        return None


def _id(value,kind):
    pattern=r"[1-5]\d{6}" if kind=="BIN" else r"\d{10}"
    return value if isinstance(value,str) and re.fullmatch(pattern,value) else None


def _get(url,query,*,client):
    if url not in {COO_URL,PLUTO_URL,OTI_URL}:
        raise ValueError("UNAPPROVED_OFFICIAL_SOURCE")
    response=client.get(
        url,params=query,timeout=15,
        headers={"Accept":"application/json","User-Agent":"EmpireAI-Bounded-Official-Property-Claims/1.0"},
    )
    response.raise_for_status()
    payload=response.content
    if not isinstance(payload,bytes) or len(payload)>MAX_RESPONSE_BYTES:
        raise ValueError("OVERSIZED_PROPERTY_SOURCE_RESPONSE")
    records=json.loads(payload)
    if (not isinstance(records,list) or len(records)>=MAX_SOURCE_ROWS
            or any(not isinstance(v,dict) for v in records)):
        raise ValueError("UNBOUNDED_OR_INVALID_PROPERTY_SOURCE_ROWS")
    return records,{
        "official_dataset_id":url.split("/")[-1].replace(".json",""),
        "official_dataset_url":url.replace("/resource/","/d/").replace(".json",""),
        "selected_request_url":getattr(response,"url",url),
        "selected_response_sha256":sha256(payload).hexdigest(),
        "observed_source_rows":len(records),
        "snapshot_scope":"SELECTED_NONPERSONAL_FIELDS_ONLY",
    }


def _validated_full_day(path:Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1_000_000:
        raise ValueError("UNTRUSTED_FULL_DAY_SOURCE")
    raw=path.read_bytes()
    report=json.loads(raw)
    if (not isinstance(report,dict) or report.get("schema")!=PREVIOUS_SCHEMA
            or report.get("coverage_state")!="FULL_ISSUED_DAY_OFFICIAL_COUNT_MATCH_AT_OBSERVATION"
            or report.get("source_permit_row_count")!=444
            or report.get("permit_event_count")!=312
            or report.get("issued_day")!="2026-10-16"
            or not isinstance(report.get("diagnostics"),list)
            or len(report["diagnostics"])!=312
            or report.get("official_day_count_before_scan")!=444
            or report.get("official_day_count_after_scan")!=444
            or report.get("external_outreach_sent") is not False
            or report.get("execution_authority")!="none"
            or report.get("source_datasets")!={
                "dob_now_filings":"w9ak-ipjd",
                "dob_now_initial_permits":"rbx6-tga4",
                "oti_building_footprints":OTI_ID,
                "dcp_pluto":PLUTO_ID,
            }):
        raise ValueError("FULL_DAY_SOURCE_CONTRACT_MISMATCH")
    # This is a hash-verified *local copy*, not proof of publisher authorship.
    prov=path.with_name(path.stem+".provenance.json")
    if prov.is_symlink() or not prov.is_file() or prov.stat().st_size>30_000:
        raise ValueError("MISSING_SOURCE_PROVENANCE")
    receipt=json.loads(prov.read_text())
    digest=sha256(raw).hexdigest()
    if (receipt.get("derived_evidence_sha256")!=digest
            or receipt.get("no_commercial_authority") is not True
            or receipt.get("source_rights_review_required") is not True):
        raise ValueError("SOURCE_DIGEST_VS_PROVENANCE_MISMATCH")
    return report,digest


def _pairs(report):
    groups=defaultdict(list)
    for d in report["diagnostics"]:
        classification=d.get("building_tax_lot_evidence_state")
        if d.get("industrial_tax_lot_context_corroborated") is True:
            target="INDUSTRIAL_CONTEXT_CORROBORATED"
        elif classification=="BUILDING_TAX_LOT_CONFLICT":
            target="DOB_OTI_BBL_UNRESOLVED"
        else:
            continue
        b=_id(d.get("permit_building_bin"),"BIN")
        lot=_id(d.get("permit_tax_lot_bbl"),"BBL")
        if not b or not lot:raise ValueError("BAD_SOURCE_REFERENCE")
        groups[(target,b,lot)].append(d)
    if (len(groups)!=4 or
        sorted(len(rows) for rows in groups.values()) != [1,1,3,8]
            or sorted(k[0] for k in groups)!=[
                "DOB_OTI_BBL_UNRESOLVED","DOB_OTI_BBL_UNRESOLVED",
                "INDUSTRIAL_CONTEXT_CORROBORATED","INDUSTRIAL_CONTEXT_CORROBORATED"
            ]):
        raise ValueError("TARGET_COHORT_CHANGED_REVIEW_REQUIRED")
    return groups


def review_property_claims(
    *, repo_root:Path=Path("/srv/empire_os"), client=requests,
    now:datetime | None=None
):
    clock=now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("NAIVE_OBSERVATION_CLOCK")
    clock=clock.astimezone(timezone.utc)
    report,report_hash=_validated_full_day(Path(repo_root)/REPORT_REL)
    groups=_pairs(report)
    bins=sorted({k[1] for k in groups})
    bbls=sorted({k[2] for k in groups} | {
        _bbl(d.get("footprint_base_bbl"))
        for rows in groups.values() for d in rows
        if _bbl(d.get("footprint_base_bbl")) is not None
    })
    pluto,pluto_receipt=_get(PLUTO_URL,{
        "$select":"bbl,borough,landuse,bldgclass,strgearea,factryarea,comarea,resarea,yearbuilt,zonedist1",
        "$where":"bbl in ("+",".join(bbls)+")","$limit":MAX_SOURCE_ROWS,
    },client=client)
    oti,oti_receipt=_get(OTI_URL,{
        "$select":"bin,base_bbl,mappluto_bbl,doitt_id,last_status_type,last_edited_date,construction_year",
        "$where":"bin in ("+",".join(bins)+")","$limit":MAX_SOURCE_ROWS,
    },client=client)
    coo,coo_receipt=_get(COO_URL,{
        "$select":"bin,bbl,c_of_o_status,c_of_o_filing_type,c_of_o_issuance_date,submitted_date,job_type",
        "$where":"bin in ("+",".join("'"+b+"'" for b in bins)+")",
        "$limit":MAX_SOURCE_ROWS,
    },client=client)

    pluto_by=defaultdict(list)
    for x in pluto:
        norm=_bbl(x.get("bbl"))
        if norm:pluto_by[norm].append(x)
    oti_by=defaultdict(list)
    for x in oti:
        bin_id=x.get("bin")
        if bin_id in bins:oti_by[bin_id].append(x)
    coo_by=defaultdict(list)
    for x in coo:
        if x.get("bin") in bins:coo_by[x["bin"]].append(x)
    claims=[]
    for (state,bin_id,lot),observations in sorted(groups.items()):
        brefs=oti_by[bin_id]
        prefs=pluto_by[lot]
        if len(brefs)!=1 or len(prefs)!=1:
            raise ValueError("OFFICIAL_REFERENCE_AMBIGUOUS_OR_MISSING")
        building=brefs[0]
        tax=prefs[0]
        same_base=_bbl(building.get("base_bbl"))==lot
        same_pluto=_bbl(building.get("mappluto_bbl"))==lot
        if state=="INDUSTRIAL_CONTEXT_CORROBORATED" and not same_pluto:
            raise ValueError("INDUSTRIAL_BBL_NO_LONGER_CROSS_AGENCY_MATCHED")
        if state=="DOB_OTI_BBL_UNRESOLVED" and (same_base or same_pluto):
            raise ValueError("RESOLVED_CONFLICT_MUST_UPDATE_BASELINE_FIRST")
        published_use=str(tax.get("landuse") or "").zfill(2)
        building_class=tax.get("bldgclass")
        if state=="INDUSTRIAL_CONTEXT_CORROBORATED" and (
            published_use!="06" or building_class not in CLASS_LABELS):
            raise ValueError("WAREHOUSE_CLASSIFICATION_NOT_REPRODUCED")
        official_area=tax.get("strgearea")
        try:
            storage_area=int(official_area) if official_area is not None else None
        except (ValueError,TypeError):
            storage_area=None
        if storage_area is not None and not 0<=storage_area<=10_000_000:
            raise ValueError("IMPLAUSIBLE_PUBLISHED_STORAGE_AREA")
        official_coo=[x for x in coo_by[bin_id]
                      if _bbl(x.get("bbl"))==lot and x.get("c_of_o_status")=="CO Issued"]
        other_coo=len(coo_by[bin_id])-len(official_coo)
        if state=="DOB_OTI_BBL_UNRESOLVED":
            # A second DOB publication does not adjudicate a contradictory OTI
            # footprint record. 'CO Issued' speaks to legal permitted use, not
            # current tenants, on-site occupation or 2026 permit activity.
            grade=("DOB_REFERENCE_CORROBORATED_OTI_CONFLICT_REMAINS"
                   if official_coo else "REFERENCE_CONFLICT_UNRESOLVED")
            allowed=["DOB_ISSUED_PERMIT_EVENT","OTI_BBL_CONFLICT_RECORDED"]
            if official_coo:allowed.append("DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT")
        else:
            grade="THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS"
            allowed=["DOB_ISSUED_PERMIT_EVENT","OTI_PLUTO_TAXLOT_REFERENCE_MATCH",
                     "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS"]
            if storage_area is not None:
                allowed.append("PLUTO_PUBLISHED_STORAGE_AREA_VALUE")
        receipts=[
            {"fact":"DOB_PERMIT_SOURCE","source_dataset_id":"rbx6-tga4",
             "source_attribution":"NYC DOB NOW Approved Permits",
             "local_full_day_report_sha256":report_hash,
             "issued_day":report["issued_day"],
             "claim_limit":"Issued event, not construction activity or a contract"},
            {"fact":"OTI_BIN_BASE_MAPPLUTO",
             "source_dataset_id":OTI_ID,
             "selected_source_response_sha256":oti_receipt["selected_response_sha256"],
             "claim_limit":"Recorded building reference, not site survey"},
            {"fact":"DCP_PLUTO_LOT_CLASS_AND_AREA",
             "source_dataset_id":PLUTO_ID,
             "selected_source_response_sha256":pluto_receipt["selected_response_sha256"],
             "claim_limit":"Tax lot/classification, not current use or operator"},
            {"fact":"DOB_NOW_COO_STATUS_FOR_SELECTED_BIN",
             "source_dataset_id":COO_ID,
             "selected_source_response_sha256":coo_receipt["selected_response_sha256"],
             "claim_limit":"Only this DOB NOW CO dataset; absence never proves unoccupied building"},
        ]
        claims.append({
            "entity_reference":{"bin":bin_id,"dob_bbl":lot,
                                "oti_physical_base_bbl":_bbl(building.get("base_bbl")),
                                "oti_pluto_join_bbl":_bbl(building.get("mappluto_bbl"))},
            "source_permit_job_references":sorted(x["permit_job_filing_ref"] for x in observations),
            "permit_events_observed":len(observations),
            "evidence_grade":grade,
            "source_landuse_code_as_reported":published_use if tax.get("landuse") else None,
            "source_dof_building_class_as_reported":building_class,
            "source_dof_building_class_label":CLASS_LABELS.get(building_class),
            "source_pluto_storage_area_as_reported":storage_area,
            "coo_issued_records_matching_same_bin_bbl":len(official_coo),
            "coo_other_records_for_same_bin":other_coo,
            "allowed_evidence_statements":allowed,
            "evidence_receipts":receipts,
            "not_proven":[
                "ACTIVE_WAREHOUSE_OPERATIONS",
                "OCCUPIED_OR_UNOCCUPIED",
                "NAMED_SITE_OWNER_OR_OPERATOR",
                "INDIVIDUAL_CUSTOMER_OR_BUYER",
                "RECENT_PHYSICAL_CONSTRUCTION_STARTED",
                "VERIFIED_REVENUE_OR_TRANSACTION",
            ],
            "customer_claim_approved":False,"outbound_authorized":False,
        })
    assert len(claims)==4
    return {
        "schema":SCHEMA,"mode":"OBSERVE","observed_at_utc":clock.isoformat(),
        "source_full_day_report_sha256":report_hash,
        "source_full_day_issued_date":report["issued_day"],
        "bounded_pair_count":len(claims),
        "source_datasets":{
            "NYC_DOB_NOW_PERMITS":"rbx6-tga4",
            "NYC_OTI_BUILDINGS":OTI_ID,
            "NYC_DCP_PLUTO":PLUTO_ID,
            "NYC_DOB_NOW_COO":COO_ID,
        },
        "additional_official_class_dictionary_url":DOF_CLASSES,
        "live_source_selected_response_receipts":[pluto_receipt,oti_receipt,coo_receipt],
        "claim_reviews":claims,
        "commercial_claim_policy":"NO_CUSTOMER_CLAIM_WITHOUT_EXACT_MATCHING_SOURCE_RECEIPT_AND_SCOPE",
        "warehouse_operations_verified_count":0,
        "ownership_or_buyer_verified_count":0,
        "external_distribution_authorized":False,
        "source_specific_licensing_review_required":True,
        "empiredb_or_signal_inbox_written":False,
        "emails_or_payments_sent":False,
        "execution_authority":"none",
    }
