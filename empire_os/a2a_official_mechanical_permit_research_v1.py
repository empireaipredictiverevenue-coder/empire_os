"""Bounded, read-only *official* Little Rock mechanical-permit business mining.

Government permit record != customer, consent, homeowner lead, purchase intent,
building project value, or proof of material demand. Stores only conservative
business-name candidates and provenance; never property/person information.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA="empire.a2a.official_little_rock_mechanical_permit_research.v1"
ENDPOINT="https://maps.littlerock.gov/server/rest/services/Permits/MapServer/0/query"
LAYER="https://maps.littlerock.gov/server/rest/services/Permits/MapServer/0"
MAX_ROWS=40
FIELDS="OBJECTID,PermitType,ContractorTrade,Contractor,PermitIssueDate,LastModifiedDate"
COMPANY_MARKERS=re.compile(
    r"\b(?:LLC|INC|CORP|CORPORATION|COMPANY|CO|LTD|MECHANICAL|HVAC|"
    r"HEATING|COOLING|AIR CONDITIONING|AIR SERVICE|AIR SERVICES|"
    r"HEAT AND AIR|HEAT & AIR|COMFORT|PLUMBING|CONSTRUCTION)\b",re.I
)
_EMAIL=re.compile(r"\S+@\S+")
_PHONE=re.compile(r"(?:\+?1[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
_USTR=re.compile(r"^[a-zA-Z0-9 &.,'-]{4,90}$")
_DATE=re.compile(r"^\d{4}-\d{2}-\d{2}")


def _company(value: Any) -> str | None:
    if not isinstance(value,str):
        return None
    name=" ".join(value.strip().split())
    if (not _USTR.fullmatch(name) or not COMPANY_MARKERS.search(name)
            or _EMAIL.search(name) or _PHONE.search(name)):
        return None
    return name


def _since(now: datetime, days: int) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("AWARE_GOV_DATA_CLOCK_REQUIRED")
    if type(days) is not int or not 7 <= days <= 60:
        raise ValueError("BOUND_GOV_DATA_LOOKBACK")
    return (now.astimezone(timezone.utc)-timedelta(days=days)).date().isoformat()


def collect_little_rock_permit_business_research(
    *, session: Any, now: datetime | None=None, lookback_days: int=45
) -> dict[str,Any]:
    clock=now or datetime.now(timezone.utc)
    start=_since(clock,lookback_days)
    params={"f":"json",
            "where":f"PermitType='MEC' AND PermitIssueDate >= '{start}'",
            "outFields":FIELDS,
            "returnGeometry":"false",
            "orderByFields":"OBJECTID DESC",
            "resultRecordCount":str(MAX_ROWS)}
    response=session.get(
        ENDPOINT, params=params, timeout=(3,13), allow_redirects=False,
        headers={"Accept":"application/json",
                 "User-Agent":"EmpireAI-Business-Research/0.1 (read-only low volume official data)"},
        stream=True)
    try:
        if response.status_code!=200:
            raise ValueError("GOV_DATA_HTTP_"+str(response.status_code))
        if "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("GOV_DATA_UNEXPECTED_CONTENT_TYPE")
        content=bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            content.extend(chunk)
            if len(content)>300_000:
                raise ValueError("GOV_DATA_RESPONSE_OVERSIZED")
        payload=json.loads(content)
    finally:
        response.close()
    if not isinstance(payload,dict) or payload.get("error"):
        raise ValueError("GOV_DATA_API_APPLICATION_ERROR")
    features=payload.get("features")
    if not isinstance(features,list) or len(features)>MAX_ROWS:
        raise ValueError("GOV_DATA_UNBOUNDED_FEATURES")
    normalized={}
    observed_dates=[]
    for feature in features:
        if not isinstance(feature,dict) or not isinstance(feature.get("attributes"),dict):
            raise ValueError("GOV_DATA_BAD_RECORD")
        a=feature["attributes"]
        pid=a.get("OBJECTID")
        if (type(pid) is not int or pid<=0
                or a.get("PermitType")!="MEC"):
            raise ValueError("GOV_DATA_SCOPE_MISMATCH")
        day=a.get("PermitIssueDate")
        if not isinstance(day,str) or not _DATE.match(day):
            continue
        dt=datetime.fromisoformat(day.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        if dt.astimezone(timezone.utc) > clock.astimezone(timezone.utc)+timedelta(days=1):
            raise ValueError("FUTURE_PERMIT_DATE")
        observed_dates.append(day[:10])
        name=_company(a.get("Contractor"))
        if name is None:
            continue
        key=" ".join(name.lower().replace(",","").replace(".","").split())
        row=normalized.setdefault(key,{
            "public_contractor_business_name_for_owner_review":name,
            "business_name_review_id":sha256(("little rock, ar|"+key).encode()).hexdigest()[:24],
            "official_permit_object_ids":[],
            "permit_activity_type":"MECHANICAL_PERMIT_ONLY_NOT_HVAC_PURCHASE_NEED",
            "permit_issue_dates":set(),
            "business_identity_independently_verified":False,
            "company_service_area_independently_verified":False,
            "lead_purchase_intent_verified":False,
            "customer_contact_authorized":False,
            "company_canonical_crm_identity_verified":False,
        })
        row["official_permit_object_ids"].append(pid)
        row["permit_issue_dates"].add(day[:10])
    companies=[]
    for row in normalized.values():
        row["official_permit_object_ids"]=sorted(set(row["official_permit_object_ids"]))[:MAX_ROWS]
        row["permit_issue_dates"]=sorted(row["permit_issue_dates"])
        companies.append(row)
    companies.sort(key=lambda x:x["business_name_review_id"])
    newest=max(observed_dates) if observed_dates else None
    age=(clock.astimezone(timezone.utc).date() -
         datetime.fromisoformat(newest).date()).days if newest else None
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "market":"little rock, ar","sector":"hvac",
        "source_layer_url":LAYER,
        "source_query_sha256":sha256(json.dumps(params,sort_keys=True).encode()).hexdigest(),
        "source_http_body_sha256":sha256(content).hexdigest(),
        "source_response_observed_at_utc":clock.astimezone(timezone.utc).isoformat(),
        "source_issuer_signature_verified":False,
        "source_terms_and_commercial_redistribution_cleared":False,
        "source_records_scanned":len(features),
        "provider_response_may_be_truncated":payload.get("exceededTransferLimit") is True,
        "conservative_business_names_retained":len(companies),
        "recent_permit_issue_date_max":newest,
        "newest_permit_age_days":age,
        "source_fresh_within_14_days":age is not None and age <= 14,
        "contractor_company_research_records":companies,
        "not_a_license_validation":True,
        "not_an_hvac_lead_feed":True,
        "new_homeowner_leads":0,
        "verified_local_hvac_lead_buyers":0,
        "verified_purchase_requirements":0,
        "personal_contacts_or_property_addresses_exported":False,
        "crm_writes":0,"outbound_messages":0,"paid_requests":0,
    }
