"""Texas research observer for the EXISTING twelve-hour EmpireOS brokerage source owner.

No second scheduler. No external customer access, identity enrichment,
commercial execution, contact extraction, or raw provider row persistence.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile
from typing import Any

import requests
from scripts.verify_texas_construction_paid_trial_source_20261117 import fetch_and_assess
from empire_os.data_brokerage_dallasnow_public import (
    review_candidates, held_review, validate_review,
)
from empire_os.data_brokerage_tdlr_public import (
    verify as verify_tdlr_registration,
    hold as held_tdlr_registration,
    validate as validate_tdlr_registration,
    CANDIDATE as TDLR_CANDIDATE,
    STATE as VERIFIED_TDLR_REGISTRATION,
)

CANONICAL = Path("/srv/empire_os")
STATE = Path("runtime/data_brokerage/texas_construction_agent_latest.json")
SCHEMA = "empire.data_brokerage.texas_construction_agent.v3"
FW_URL = ("https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/"
          "CFW_Open_Data_Development_Permits_View/FeatureServer/0/query")
FW_FIELDS = "Permit_No,Permit_Type,Current_Status,Status_Date,File_Date,Use_Type,Specific_Use"
FW_CAP = 20
REF = re.compile(r"[A-Za-z0-9_.-]{4,80}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
DALLAS_ALLOWED = frozenset((
    "schema_version","status","execution_authority","source_url","source_api_url",
    "period","observed_at","source_response_sha256","source_count_response_sha256",
    "bounded_query_total","rows_accepted","source_rows_complete_for_filter",
    "source_field_presence","source_reported_dates","actual_issuance_status_verified",
    "text_mentions_not_verified_classification","internal_keyword_candidates",
    "unreviewed_keyword_matches","requested_texas_project_area_supported",
    "other_texas_jurisdictions_covered","project_hotel_apartment_mix_verified",
    "developer_or_owner_verified","start_completion_dates_verified",
    "active_build_stage_verified","architect_general_contractor_verified",
    "decision_maker_identity_verified","contact_permission_verified",
    "fitness_facility_verified","buyer_budget_or_order_verified",
    "source_reuse_rights_cleared","crm_write","outreach_sent",
    "customer_delivery_enabled",
))
FORT_ALLOWED = frozenset((
    "status","source_url","source_response_sha256","month",
    "source_rows_sampled","source_rows_accepted_after_quarantine",
    "source_future_or_invalid_rows_quarantined","distinct_permits_in_sample",
    "duplicate_permit_rows","sample_may_be_incomplete",
    "original_issue_date_verified","status_changed_dates",
    "original_filing_year_counts","commercial_permit_types",
    "named_people_or_property_addresses_saved",
    "company_buying_intent_verified","customer_delivery_enabled",
))
GATES = {
    "buyer_qualified": False,
    "business_identity_verified": False,
    "decision_maker_contact_verified": False,
    "independent_dallas_project_status_verified": False,
    "source_resale_rights_cleared": False,
    "crm_write": False,
    "outbound_sent": False,
    "customer_delivery_enabled": False,
    "execution_authority": "none",
}

def digest(value: dict) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
                             allow_nan=False).encode()).hexdigest()

def _date_ms(value: Any, *, now: datetime) -> str:
    if type(value) is not int or value <= 0:
        raise ValueError("FORT_WORTH_DATE_MISSING")
    try:
        date = datetime.fromtimestamp(value/1000, timezone.utc)
    except (OSError, OverflowError, ValueError) as exc:
        raise ValueError("FORT_WORTH_DATE_OUT_OF_RANGE") from exc
    if date > now + timedelta(days=1) or date.year < 2000:
        raise ValueError("FORT_WORTH_DATE_UNTRUSTED")
    return date.date().isoformat()

def read_fortworth_month(*, now: datetime, request_get=None, timeout=8) -> dict:
    if now.utcoffset() is None or not 1 <= timeout <= 10:
        raise ValueError("FORT_WORTH_CLOCK_OR_TIMEOUT_INVALID")
    month = now.astimezone(timezone.utc).strftime("%Y-%m")
    params = {
        "f":"json",
        "where":(
            "Current_Status = 'Issued' AND "
            f"Status_Date >= DATE '{month}-01 00:00:00' "
            "AND Permit_Type LIKE '%Commercial%'"
        ),
        "outFields":FW_FIELDS,
        "orderByFields":"Status_Date DESC,Permit_No ASC",
        "resultRecordCount":FW_CAP,
        "returnGeometry":"false",
    }
    get = request_get or requests.get
    r=get(FW_URL,params=params,timeout=timeout,allow_redirects=False,
          headers={"Accept":"application/json"})
    if (r.status_code!=200 or len(r.content)>100_000
        or not r.headers.get("Content-Type","").startswith("application/json")):
        raise ValueError("FORT_WORTH_SOURCE_HTTP_HOLD")
    try:
        body=json.loads(r.content)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("FORT_WORTH_BAD_JSON") from exc
    if not isinstance(body,dict) or body.get("error"):
        raise ValueError("FORT_WORTH_PROVIDER_ERROR")
    rows=body.get("features")
    if not isinstance(rows,list) or len(rows)>FW_CAP:
        raise ValueError("FORT_WORTH_SOURCE_BOUND_HOLD")
    refs=[]; updates=[]; filed=[]; types=Counter()
    quarantined=0
    for item in rows:
        row=item.get("attributes") if isinstance(item,dict) else None
        if not isinstance(row,dict) or not set(row).issubset(FW_FIELDS.split(",")):
            raise ValueError("FORT_WORTH_FIELDS_UNTRUSTED")
        ref=row.get("Permit_No"); typ=row.get("Permit_Type")
        if (not isinstance(ref,str) or not REF.fullmatch(ref)
            or not isinstance(typ,str) or len(typ)>100
            or "Commercial" not in typ or row.get("Current_Status")!="Issued"):
            raise ValueError("FORT_WORTH_SOURCE_NOT_COMMERCIAL_ISSUED")
        try:
            changed=_date_ms(row.get("Status_Date"),now=now)
            original=_date_ms(row.get("File_Date"),now=now)
            if (changed < month+"-01" or changed > now.date().isoformat()
                or original > changed):
                raise ValueError("FORT_WORTH_SOURCE_OUT_OF_PERIOD")
        except ValueError:
            # Official sources can contain future-dated status records.
            # Quarantine them instead of turning them into fake opportunities.
            quarantined+=1
            continue
        refs.append(ref); updates.append(changed); filed.append(original)
        types[typ]+=1
    if not refs or quarantined > 5:
        raise ValueError("FORT_WORTH_SAMPLE_TOO_MANY_UNTRUSTED_RECORDS")
    return {
        "status":"FORT_WORTH_STATUS_UPDATE_SAMPLE_NOT_NEW_ISSUANCES",
        "source_url":FW_URL,
        "source_response_sha256":sha256(r.content).hexdigest(),
        "month":month,
        "source_rows_sampled":len(rows),
        "source_rows_accepted_after_quarantine":len(refs),
        "source_future_or_invalid_rows_quarantined":quarantined,
        "distinct_permits_in_sample":len(set(refs)),
        "duplicate_permit_rows":len(refs)-len(set(refs)),
        "sample_may_be_incomplete":len(rows)==FW_CAP or body.get("exceededTransferLimit") is True,
        "original_issue_date_verified":False,
        "status_changed_dates":dict(sorted(Counter(updates).items())),
        "original_filing_year_counts":dict(sorted(Counter(x[:4] for x in filed).items())),
        "commercial_permit_types":dict(sorted(types.items())),
        "named_people_or_property_addresses_saved":False,
        "company_buying_intent_verified":False,
        "customer_delivery_enabled":False,
    }

def validate_state(value: Any, *, now: datetime) -> bool:
    if not isinstance(value,dict) or now.utcoffset() is None:
        return False
    expected_top={
        "schema_version","mode","status","observed_at","owner",
        "dallas","fort_worth","dallasnow","tdlr_registration","dallas_change_since_prior_valid_cycle",
        "buyer_fit","next_internal_research_actions","execution_trigger",*GATES,
    }
    if (set(value)!=expected_top
        or value.get("execution_trigger") not in (
            "MANUAL_OWNER_BOOTSTRAP", "ORIGINAL_BROKERAGE_CYCLE",
            "ORIGINAL_BROKERAGE_COOLDOWN_RETRY")
        or value.get("schema_version")!=SCHEMA
        or value.get("mode")!="INTERNAL_SOURCE_RESEARCH"
        or value.get("status") not in (
            "TEXAS_AGENT_DALLAS_AND_FORT_WORTH_RESEARCH_VERIFIED",
            "TEXAS_AGENT_DALLAS_VERIFIED_FORT_WORTH_HELD")
        or any(value.get(key)!=expected for key,expected in GATES.items())):
        return False
    try:
        stamp=datetime.fromisoformat(value["observed_at"])
    except (ValueError,KeyError,TypeError):
        return False
    if stamp.utcoffset() is None or stamp>now or now-stamp>timedelta(hours=40):
        return False
    dallas=value.get("dallas")
    if (not isinstance(dallas,dict) or set(dallas)!=DALLAS_ALLOWED
        or dallas.get("status")!="SOURCE_VALIDATED_COMMERCIAL_BUYER_FIT_NOT_VERIFIED"
        or dallas.get("period")!=stamp.strftime("%Y-%m")
        or type(dallas.get("rows_accepted")) is not int
        or dallas.get("bounded_query_total")!=dallas["rows_accepted"]
        or dallas.get("actual_issuance_status_verified") is not False
        or not 0<=dallas["rows_accepted"]<=40
        or dallas.get("source_rows_complete_for_filter") is not (dallas["rows_accepted"]<40)
        or not DIGEST.fullmatch(str(dallas.get("source_response_sha256","")))
        or not DIGEST.fullmatch(str(dallas.get("source_count_response_sha256","")))
        or any(dallas.get(key) is not False for key in (
            "buyer_budget_or_order_verified", "customer_delivery_enabled",
            "decision_maker_identity_verified","crm_write","outreach_sent"))):
        return False
    accepted=frozenset((
        "source_permit_reference","source_reported_date",
        "description_keyword_flags_not_verified_project_types",
        "official_land_use_field","source_dataset","developer_verified",
        "current_construction_stage_verified",
        "specifier_or_decision_maker_verified",
        "gym_requirement_verified","outreach_authorised",
    ))
    rows=dallas.get("internal_keyword_candidates")
    if not isinstance(rows,list) or len(rows)>8:
        return False
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!=accepted:
            return False
        ref=row.get("source_permit_reference")
        if (not isinstance(ref,str) or not REF.fullmatch(ref) or ref in seen
            or any(row.get(key) is not False for key in (
                "developer_verified","current_construction_stage_verified",
                "specifier_or_decision_maker_verified",
                "gym_requirement_verified","outreach_authorised"))
            or not isinstance(row.get("description_keyword_flags_not_verified_project_types"),list)
            or not all(x in ("HOTEL_TEXT_MENTION","MULTIFAMILY_TEXT_MENTION",
                             "FITNESS_TEXT_MENTION")
                       for x in row["description_keyword_flags_not_verified_project_types"])):
            return False
        seen.add(ref)
    fort=value.get("fort_worth")
    if not isinstance(fort,dict) or fort.get("status") not in (
        "FORT_WORTH_STATUS_UPDATE_SAMPLE_NOT_NEW_ISSUANCES",
        "FORT_WORTH_OFFICIAL_SOURCE_HOLD"):
        return False
    if fort["status"]=="FORT_WORTH_STATUS_UPDATE_SAMPLE_NOT_NEW_ISSUANCES":
        if (set(fort)!=FORT_ALLOWED
            or fort.get("original_issue_date_verified") is not False
            or fort.get("named_people_or_property_addresses_saved") is not False
            or fort.get("customer_delivery_enabled") is not False
            or fort.get("company_buying_intent_verified") is not False
            or fort.get("month")!=dallas["period"]
            or not DIGEST.fullmatch(str(fort.get("source_response_sha256","")))
            or type(fort.get("source_rows_sampled")) is not int
            or not 0<=fort["source_rows_sampled"]<=FW_CAP
            or type(fort.get("source_rows_accepted_after_quarantine")) is not int
            or type(fort.get("source_future_or_invalid_rows_quarantined")) is not int
            or (fort["source_rows_accepted_after_quarantine"]
                +fort["source_future_or_invalid_rows_quarantined"]
                !=fort["source_rows_sampled"])):
            return False
    else:
        if set(fort)!={"status","source_rows_sampled",
                      "independent_fort_worth_source_verified"}:
            return False
    official_refs=[row["source_permit_reference"] for row in rows]
    if not validate_review(value.get("dallasnow"),expected_refs=official_refs):
        return False
    if not validate_tdlr_registration(value.get("tdlr_registration")):
        return False
    delta=value.get("dallas_change_since_prior_valid_cycle")
    if (not isinstance(delta,dict)
        or type(delta.get("newly_observed_keyword_permit_refs")) is not int
        or delta["newly_observed_keyword_permit_refs"]<0
        or delta.get("permit_ref_is_proven_buyer") is not False):
        return False
    if value.get("buyer_fit") != {
        "confirmed_customer_order":False,
        "texas_statewide_coverage_verified":False,
        "hotel_multifamily_project_type_independently_verified":False,
        "developer_contact_verified":False,
        "construction_stage_verified":False,
        "source_rights_for_customer_delivery_verified":False,
        "pilot_ready":False,
    }:
        return False
    return True

def load_state(root: Path, *, now: datetime) -> dict | None:
    location=root/STATE
    try:
        if (location.is_symlink() or location.stat().st_size>35000
            or location.stat().st_mode & 0o077):
            return None
        data=json.loads(location.read_text(encoding="utf-8"))
        checksum=data.pop("integrity_sha256")
        if (not isinstance(checksum,str) or not DIGEST.fullmatch(checksum)
            or digest(data)!=checksum or not validate_state(data,now=now)):
            return None
        return {**data,"integrity_sha256":checksum}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return None

def persist_state(root: Path, value:dict, *, now:datetime) -> Path:
    if root.resolve()!=CANONICAL or not validate_state(value,now=now):
        raise ValueError("ORIGINAL_TEXAS_SOURCE_OWNER_AUTHORITY_HOLD")
    location=root/STATE
    if location.is_symlink() or location.parent.is_symlink():
        raise ValueError("PRIVATE_SOURCE_SYMLINK_HOLD")
    location.parent.mkdir(parents=True,exist_ok=True)
    os.chmod(location.parent,0o700)
    content={**value,"integrity_sha256":digest(value)}
    fd,temporary=tempfile.mkstemp(prefix=".texas_agent_",dir=location.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as output:
            json.dump(content,output,sort_keys=True,allow_nan=False,indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary,location)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return location

def run_texas_research(
    root:Path, *, now:datetime, persist:bool=False,
    dallas_reader=None, fortworth_reader=None, dallasnow_reviewer=None, tdlr_reviewer=None,
    trigger: str = "MANUAL_OWNER_BOOTSTRAP",
) -> dict:
    """Existing Data Brokerage calls this under its own 12-hour owner lock.

    A read-only canary is persist=False and never writes. Exactly one saved
    state is owned by the canonical brokerage cycle, not a second service.
    """
    root=Path(root).resolve()
    if (now.utcoffset() is None or (persist and root!=CANONICAL)
        or trigger not in ("MANUAL_OWNER_BOOTSTRAP", "ORIGINAL_BROKERAGE_CYCLE",
                           "ORIGINAL_BROKERAGE_COOLDOWN_RETRY")):
        raise ValueError("TEXAS_CANONICAL_OWNER_OR_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    month=now.strftime("%Y-%m")
    dallas_read=dallas_reader or (
        lambda: fetch_and_assess(now=now,month=month,timeout=8)
    )
    fw_read=fortworth_reader or (
        lambda: read_fortworth_month(now=now,timeout=8)
    )
    try:
        dallas=dallas_read()
    except (OSError,ValueError,TypeError,KeyError,requests.RequestException):
        return {
            "status":"DALLAS_OFFICIAL_SOURCE_HOLD",
            "texas_source_month":month,
            "source_receipts_committed":False,
            "execution_authority":"none",
            "outreach_sent":False,
        }
    try:
        fort=fw_read()
    except (OSError,ValueError,TypeError,KeyError,requests.RequestException):
        fort={
            "status":"FORT_WORTH_OFFICIAL_SOURCE_HOLD",
            "source_rows_sampled":0,
            "independent_fort_worth_source_verified":False,
        }
    # Source-status corroboration is read-only, using City of Dallas's public
    # no-login portal. Five records max, two new ref lookups max per cycle.
    # Injected readers are test-only; never make external requests in unit tests.
    if dallasnow_reviewer is not None:
        city_review=dallasnow_reviewer(dallas["internal_keyword_candidates"])
    elif dallas_reader is None and fortworth_reader is None:
        try:
            city_review=review_candidates(dallas["internal_keyword_candidates"])
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
            city_review=held_review(len(dallas["internal_keyword_candidates"]))
    else:
        city_review=held_review(len(dallas["internal_keyword_candidates"]))
    if not validate_review(
        city_review,
        expected_refs=[r["source_permit_reference"]
                       for r in dallas["internal_keyword_candidates"]]
    ):
        raise ValueError("DALLASNOW_CITY_SOURCE_VERIFICATION_INVALID")
    linked_city_status=any(
        row.get("permit_reference")==TDLR_CANDIDATE
        and row.get("official_record_status_independently_verified") is True
        for row in city_review["records"]
    )
    if linked_city_status:
        if tdlr_reviewer is not None:
            state_project=tdlr_reviewer()
        elif dallas_reader is None and fortworth_reader is None:
            try:
                state_project=verify_tdlr_registration(now=now)
            except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
                state_project=held_tdlr_registration()
        else:
            state_project=held_tdlr_registration()
    else:
        state_project=held_tdlr_registration()
    if not validate_tdlr_registration(state_project):
        raise ValueError("TEXAS_STATE_PUBLIC_REGISTRATION_EVIDENCE_INVALID")
    previous=load_state(root,now=now)
    old_refs={
        x["source_permit_reference"]
        for x in ((previous or {}).get("dallas") or {}).get("internal_keyword_candidates",[])
    }
    new_refs=[
        x["source_permit_reference"]
        for x in dallas.get("internal_keyword_candidates",[])
        if x["source_permit_reference"] not in old_refs
    ]
    newly_observed=len(new_refs) if previous else 0
    state={
        "schema_version":SCHEMA,
        "mode":"INTERNAL_SOURCE_RESEARCH",
        "execution_trigger":trigger,
        "status":(
            "TEXAS_AGENT_DALLAS_AND_FORT_WORTH_RESEARCH_VERIFIED"
            if fort["status"]=="FORT_WORTH_STATUS_UPDATE_SAMPLE_NOT_NEW_ISSUANCES"
            else "TEXAS_AGENT_DALLAS_VERIFIED_FORT_WORTH_HELD"
        ),
        "observed_at":now.isoformat(),
        "owner":"original_data_brokerage_source_mining_12hour",
        "dallas":dallas,
        "fort_worth":fort,
        "dallasnow":city_review,
        "tdlr_registration":state_project,
        "dallas_change_since_prior_valid_cycle":{
            "prior_valid_observation":previous is not None,
            "newly_observed_keyword_permit_refs":newly_observed,
            "new_keyword_refs_research_only":new_refs[:8] if previous else [],
            "permit_ref_is_proven_buyer":False,
        },
        "buyer_fit":{
            "confirmed_customer_order":False,
            "texas_statewide_coverage_verified":False,
            "hotel_multifamily_project_type_independently_verified":False,
            "developer_contact_verified":False,
            "construction_stage_verified":False,
            "source_rights_for_customer_delivery_verified":False,
            "pilot_ready":False,
        },
        "next_internal_research_actions":[
            "RECHECK_DALLASNOW_PUBLIC_RECORD_STATUS_WITHOUT_ASSUMING_ISSUANCE",
            "RECONCILE_TDLR_STATE_REGISTRATION_AND_DALLAS_PERMIT_LOCATION_MISMATCH",
            "RECONCILE_CURRENT_CONSTRUCTION_STAGE_WITH_PRIMARY_CITY_RECORD",
            "REVIEW_DATA_RIGHTS_AND_FIELD_LEVEL_PERMISSION",
            "RECONCILE_EXISTING_CRM_AND_SUPPRESSION_BEFORE_OUTBOUND_APPROVAL",
        ],
        **GATES,
    }
    if not validate_state(state,now=now):
        raise ValueError("TEXAS_AGENT_RESEARCH_EVIDENCE_QUALITY_HOLD")
    if persist:
        persist_state(root,state,now=now)
    return {
        "status":state["status"],
        "execution_trigger":trigger,
        "texas_source_month":month,
        "dallas_permits_count":dallas["rows_accepted"],
        "dallas_keyword_research_candidates":len(dallas["internal_keyword_candidates"]),
        "dallasnow_official_statuses_verified":city_review["verified_record_status_count"],
        "dallasnow_record_status_fingerprint":city_review["record_status_fingerprint"],
        "dallasnow_issuance_dates_verified":0,
        "state_tdlr_registration_verified":(
            state_project["status"]==VERIFIED_TDLR_REGISTRATION),
        "state_tdlr_city_project_link_held":True,
        "fort_worth_recent_status_rows":fort.get("source_rows_accepted_after_quarantine",0),
        "fort_worth_future_or_invalid_quarantined":fort.get(
            "source_future_or_invalid_rows_quarantined",0),
        "fort_worth_is_not_a_dallas_corrob_source":True,
        "newly_observed_keyword_ref_changes":newly_observed,
        "buyer_fulfilment_ready":False,
        "source_receipts_committed":persist,
        "execution_authority":"none",
        "outreach_sent":False,
    }
