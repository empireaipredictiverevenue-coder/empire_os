"""Three-agency official permit -> building -> tax lot research, OBSERVE only.

NYC DOB NOW event / NYC OTI building footprints / NYC DCP PLUTO.
Source-match identities and land-use categories are NEVER company/customer
identities. Building-footprint BIN mismatch to DOB tax-lot BBL is a hold.
No personal/contact fields, raw geometry or street address ever requested.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping
import json
import re

import requests

from empire_os.lead_sources.nyc_dobnow import JOB

SCHEMA = "empire.permit_property_three_agency_evidence.v1"
FOOTPRINT_ID = "5zhs-2jue"
PLUTO_ID = "64uk-42ks"
FOOTPRINT_URL = f"https://data.cityofnewyork.us/resource/{FOOTPRINT_ID}.json"
PLUTO_URL = f"https://data.cityofnewyork.us/resource/{PLUTO_ID}.json"
MAX_EVENTS = 40
MAX_SOURCE_ROWS = 120
MAX_BYTES = 200_000
BOROUGH = {
    "Manhattan": "MN", "Bronx": "BX", "Brooklyn": "BK",
    "Queens": "QN", "Staten Island": "SI",
}
# Source-defined PLUTO land-use categories; '06' means industrial &
# manufacturing *tax lot*, NOT a verified functioning warehouse.
LAND_USE = {
    "01": "ONE_TWO_FAMILY",
    "02": "MULTIFAMILY_WALKUP",
    "03": "MULTIFAMILY_ELEVATOR",
    "04": "MIXED_RESIDENTIAL_COMMERCIAL",
    "05": "COMMERCIAL_OFFICE",
    "06": "INDUSTRIAL_MANUFACTURING",
    "07": "TRANSPORT_UTILITY",
    "08": "PUBLIC_INSTITUTIONAL",
    "09": "OPEN_SPACE_RECREATION",
    "10": "PARKING",
    "11": "VACANT_LOT",
}
LOT_RE = re.compile(r"\d{10}\Z")
BIN_RE = re.compile(r"[1-5]\d{6}\Z")
CLASS_RE = re.compile(r"[A-Z0-9]{1,3}\Z")


def _id(value: Any, pattern: re.Pattern) -> str | None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        return None
    return value


def _lot(value: Any) -> str | None:
    """Normalize decimal PLUTO BBL without float precision loss."""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    try:
        d=Decimal(str(value))
    except InvalidOperation:
        return None
    if not d.is_finite() or d != d.to_integral_value():
        return None
    result=str(int(d))
    return result if LOT_RE.fullmatch(result) else None


def _borough(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned=value.strip().upper()
    if cleaned in {"MN","BX","BK","QN","SI"}:
        return cleaned
    for name,short in BOROUGH.items():
        if cleaned==name.upper():
            return short
    return None


def _landuse(value: Any) -> str | None:
    if not isinstance(value,(str,int)) or isinstance(value,bool):
        return None
    v=str(value).strip().zfill(2)
    return v if v in LAND_USE else None


def _nonnegative_num(value: Any) -> float | None:
    """For ranking context only; never treat optional area as property fact."""
    if not isinstance(value,(str,int,float)) or isinstance(value,bool):
        return None
    try:
        d=Decimal(str(value))
    except InvalidOperation:
        return None
    if not d.is_finite() or d<0 or d>10**10:
        return None
    return float(d)


def _read_source(url: str, params: dict, *, client=requests) -> tuple[list[dict],dict]:
    if url not in {FOOTPRINT_URL,PLUTO_URL}:
        raise ValueError("UNAPPROVED_NYC_PROPERTY_PROVIDER_URL")
    r=client.get(url,params=params,timeout=15,headers={
        "Accept":"application/json",
        "User-Agent":"EmpireAI-Bounded-Source-Review/1.0",
    })
    r.raise_for_status()
    body=r.content
    if not isinstance(body,bytes) or len(body)>MAX_BYTES:
        raise ValueError("OVERSIZED_OFFICIAL_PROPERTY_RESPONSE")
    rows=json.loads(body)
    if (not isinstance(rows,list) or len(rows)>MAX_SOURCE_ROWS
            or any(not isinstance(x,dict) for x in rows)):
        raise ValueError("MALFORMED_OFFICIAL_PROPERTY_ROWS")
    return rows, {
        "dataset_id": FOOTPRINT_ID if url==FOOTPRINT_URL else PLUTO_ID,
        "query_url": r.url if isinstance(getattr(r,"url",None),str)
                     and r.url.startswith(url+"?") else url,
        "selected_response_sha256":sha256(body).hexdigest(),
        "selected_rows_returned":len(rows),
    }


def _valid_event(event: Mapping[str,Any]) -> bool:
    return bool(
        isinstance(event,dict)
        and isinstance(event.get("job_filing_number"),str)
        and JOB.fullmatch(event["job_filing_number"])
        and _id(event.get("bin"),BIN_RE)
        and _id(event.get("bbl"),LOT_RE)
        and _borough(event.get("borough")) is not None
        and event.get("official_event_crosscheck") is True
        and event.get("filing_reason") == "Initial Permit"
        and event.get("permit_status") == "Permit Issued"
        and isinstance(event.get("issued_date"),str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}",event["issued_date"])
    )


def review_official_building_landuse(
    events: list[dict], *, now: datetime | None = None, client=requests,
) -> dict[str,Any]:
    """Selected-field external read only; returns original derived diagnostics.

    Never assumes every DOB job is one unique construction site; linked
    counts are event-level, and a tax lot can include multiple buildings.
    """
    if not isinstance(events,list) or not 1<=len(events)<=MAX_EVENTS:
        raise ValueError("UNBOUNDED_PERMIT_PROPERTY_REVIEW")
    if any(not _valid_event(e) for e in events):
        raise ValueError("UNTRUSTED_SOURCE_EVENTS")
    jobs=[e["job_filing_number"] for e in events]
    if len(jobs)!=len(set(jobs)):
        raise ValueError("DUPLICATE_JOB_IN_REVIEW")
    stamp=now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("OBSERVATION_CLOCK_MUST_BE_UTC_AWARE")
    bins=sorted({e["bin"] for e in events})
    bbls=sorted({e["bbl"] for e in events})
    # IDs are validated digits: no source-controlled string SQL fragments.
    pfoot={
        "$select":"bin,base_bbl,doitt_id,construction_year,last_status_type",
        "$where":"bin in ("+",".join(bins)+")",
        "$limit":MAX_SOURCE_ROWS,
    }
    plot={
        "$select":"bbl,borough,landuse,bldgclass,comarea,resarea,strgearea,factryarea,yearbuilt",
        "$where":"bbl in ("+",".join(bbls)+")",
        "$limit":MAX_SOURCE_ROWS,
    }
    footprints,foot_receipt=_read_source(FOOTPRINT_URL,pfoot,client=client)
    lots,lot_receipt=_read_source(PLUTO_URL,plot,client=client)
    # A hit at the response cap could omit relevant duplicate source rows
    # and falsely make an ambiguous BIN look unique.
    if len(footprints)==MAX_SOURCE_ROWS or len(lots)==MAX_SOURCE_ROWS:
        raise ValueError("TRUNCATED_PROPERTY_SOURCE_RESULT")
    seen_bins=set(bins);seen_lots=set(bbls)
    bin_rows=defaultdict(list)
    for f in footprints:
        b=_id(f.get("bin"),BIN_RE)
        if b is not None and b in seen_bins:
            bin_rows[b].append(f)
    lot_rows=defaultdict(list)
    for l in lots:
        b=_lot(l.get("bbl"))
        if b is not None and b in seen_lots:
            lot_rows[b].append(l)
    diagnostics=[]
    stats=Counter()
    use_counts=Counter()
    for ev in events:
        fs=bin_rows.get(ev["bin"],[])
        ps=lot_rows.get(ev["bbl"],[])
        # Source hit count 2+ is ambiguity, NOT a reason to take first.
        if len(fs)>1 or len(ps)>1:
            state="AMBIGUOUS_SOURCE_IDENTITY"
        elif fs and ps:
            same_lot=(_lot(fs[0].get("base_bbl")) == ev["bbl"])
            state=("TRI_AGENCY_BIN_AND_LOT_MATCH" if same_lot
                   else "BUILDING_TAX_LOT_CONFLICT")
        elif ps:
            state="DCP_LOT_ONLY_BIN_UNCONFIRMED"
        elif fs:
            state="OTI_BIN_ONLY_TAX_LOT_UNCONFIRMED"
        else:
            state="PROPERTY_SOURCE_REFERENCE_UNMATCHED"
        p=ps[0] if len(ps)==1 else None
        code=_landuse(p.get("landuse")) if p and _borough(p.get("borough"))==_borough(ev["borough"]) else None
        if p is not None and _borough(p.get("borough"))!=_borough(ev["borough"]):
            state="DCP_BOROUGH_CONFLICT"
        taxon=LAND_USE[code] if code else "UNKNOWN"
        # These are LOT-level categories even when footprint BIN matches.
        bclass=(str(p.get("bldgclass")).strip().upper()
                if p and isinstance(p.get("bldgclass"),str) else "")
        if not CLASS_RE.fullmatch(bclass):
            bclass=None
        industrial=bool(code=="06" and state=="TRI_AGENCY_BIN_AND_LOT_MATCH")
        item={
            "permit_job_filing_ref":ev["job_filing_number"],
            "permit_original_issued_date":ev["issued_date"],
            "permit_building_bin":ev["bin"],
            "permit_tax_lot_bbl":ev["bbl"],
            "matching_footprint_source_rows":len(fs),
            "matching_dcp_lot_source_rows":len(ps),
            "building_tax_lot_evidence_state":state,
            "dcp_land_use_code":code,
            "dcp_land_use_category":taxon,
            "dcp_building_class":bclass,
            "footprint_base_bbl":_lot(fs[0].get("base_bbl")) if len(fs)==1 else None,
            "industrial_tax_lot_context_corroborated":industrial,
            "warehouse_operation_verified":False,
            "building_owner_identity_verified":False,
            "verified_business_buyer":False,
            "property_transaction_verified":False,
            "property_damage_verified":False,
            "commercial_contact_authorized":False,
        }
        diagnostics.append(item)
        stats[state]+=1
        use_counts[taxon]+=1
    if len(diagnostics)!=len(events):
        raise ValueError("INCOMPLETE_PROPERTY_REVIEW")
    return {
        "schema":SCHEMA,
        "mode":"OBSERVE",
        "reviewed_at_utc":stamp.astimezone(timezone.utc).isoformat(),
        "source_datasets":{
            "dob_now_filings":"w9ak-ipjd",
            "dob_now_initial_permits":"rbx6-tga4",
            "oti_building_footprints":FOOTPRINT_ID,
            "dcp_pluto":"64uk-42ks",
        },
        "agency_levels":["DOB","OTI","DCP"],
        "source_selected_response_receipts":[foot_receipt,lot_receipt],
        "permit_event_count":len(events),
        "event_level_join_status_counts":dict(sorted(stats.items())),
        "event_level_landuse_category_counts":dict(sorted(use_counts.items())),
        "event_level_industrial_lot_context_count":sum(
            x["industrial_tax_lot_context_corroborated"] for x in diagnostics
        ),
        "diagnostics":sorted(diagnostics,key=lambda x:x["permit_job_filing_ref"]),
        "source_freshness_caveat":(
            "OTI footprints Oct 2026 and DCP PLUTO 26v2 Aug 2026 are not "
            "physical-site or owner inspections; dates and coverage differ."
        ),
        "truth_limitations":[
            "Official DOB job events are not uniquely identified physical buildings.",
            "Exact DOB BIN-to-OTI BIN and OTI base BBL-to-DCP lot only validates a source reference chain.",
            "DCP PLUTO landuse describes a tax lot, not the operating use of an individual building.",
            "No consumer identity, business buyer, warehouse operator, paid customer or revenue verified.",
        ],
        "rights_review_required_for_customer_distribution":True,
        "external_outreach_sent":False,
        "data_warehouse_or_empiredb_mutated":False,
        "paid_provider_used":False,
        "execution_authority":"none",
    }
