"""Official Texas accessibility-project registration check (internal evidence only).

The state registration is an INDEPENDENT project record, not proof that a
differently addressed Dallas permit belongs to that state project. Do not
extract or save people, emails, phones, addresses or organisations.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import re
import requests
from bs4 import BeautifulSoup

SOURCE="https://www.tdlr.texas.gov/TABS/Search/Project/TABS2027002235"
ID="TABS2027002235"
CANDIDATE="COM-NEW-26-000365"
STATE="STATE_REGISTRATION_VERIFIED_UNLINKED_CITY_PERMIT"
HOLD="STATE_REGISTRATION_UNAVAILABLE_OR_UNLINKED"

def hold() -> dict:
    return {
        "status":HOLD,
        "state_project_id":ID,
        "potential_city_permit_reference":CANDIDATE,
        "same_project_as_city_permit_verified":False,
        "buyer_identity_verified":False,
        "owner_or_contact_names_persisted":False,
        "planned_dates_not_actual_construction":True,
    }

def verify(*, now:datetime, session=None, timeout=8) -> dict:
    if now.utcoffset() is None or not 2<=timeout<=10:
        raise ValueError("STATE_PROJECT_CLOCK_OR_BUDGET_INVALID")
    now=now.astimezone(timezone.utc)
    source=session or requests
    r=source.get(SOURCE,timeout=timeout,allow_redirects=False,
                 headers={"Accept":"text/html","User-Agent":"EmpireAI-Brokerage-PublicSourceQuality/1.0"})
    if (r.status_code!=200 or not r.headers.get("Content-Type","").startswith("text/html")
        or not 1000<len(r.content)<=100000):
        raise ValueError("STATE_REGISTRATION_SOURCE_UNAVAILABLE")
    soup=BeautifulSoup(r.text,"html.parser")
    values={}
    for dt in soup.find_all("dt"):
        label=dt.get_text(" ",strip=True).strip().rstrip(":")
        if label not in (
            "Project Name","Project Number","Location Address",
            "Start Date","Completion Date","Estimated Cost","Type of Work",
            "Scope of Work","Current Status","Owner Name","Design Firm Name",
        ):
            continue
        node=dt.find_next_sibling("dd")
        value=node.get_text(" ",strip=True) if node else ""
        if label in values:
            raise ValueError("AMBIGUOUS_STATE_PROJECT_FIELD")
        values[label]=value
    if (values.get("Project Number")!=ID
        or values.get("Project Name")!="Mockingbird Oak Park - Multifamily"
        or values.get("Type of Work")!="New Construction"
        or values.get("Current Status")!="Project Registered"):
        raise ValueError("STATE_PROJECT_ID_OR_STAGE_MISMATCH")
    if (not values.get("Location Address","").lower().startswith("1545 mockingbird ln")
        or not values.get("Owner Name")
        or not values.get("Design Firm Name")):
        raise ValueError("STATE_PROJECT_IDENTITY_OR_LOCATION_HOLD")
    scope=values.get("Scope of Work","")
    unitmatch=re.search(r"Multifamily Apartments\s*\((\d{1,5}) units\b",scope,re.I)
    if unitmatch is None or int(unitmatch.group(1))!=359:
        raise ValueError("STATE_PROJECT_UNITS_UNVERIFIED")
    try:
        start=datetime.strptime(values["Start Date"],"%m/%d/%Y").date()
        finish=datetime.strptime(values["Completion Date"],"%m/%d/%Y").date()
        cost_text=values["Estimated Cost"]
        if not re.fullmatch(r"\$[0-9,]{5,14}",cost_text):
            raise ValueError("COST_FORMAT_UNTRUSTED")
        cost=int(cost_text.replace("$","").replace(",",""))
    except (KeyError,ValueError,TypeError) as exc:
        raise ValueError("STATE_PROJECT_DATES_OR_COST_INVALID") from exc
    if start.year<2026 or not start<finish or cost<1_000_000 or cost>250_000_000:
        raise ValueError("STATE_PROJECT_SCOPE_UNTRUSTED")
    return {
        "status":STATE,
        "state_project_id":ID,
        "source_url":SOURCE,
        "source_response_sha256":sha256(r.content).hexdigest(),
        "state_project_name_verified":True,
        "state_project_registration_status":"Project Registered",
        "state_project_type":"MULTIFAMILY_APARTMENTS",
        "state_registered_apartment_units":359,
        "state_planned_construction_start":start.isoformat(),
        "state_planned_completion":finish.isoformat(),
        "state_registered_estimate_usd":cost,
        "state_owner_organisation_field_present":True,
        "state_design_firm_field_present":True,
        "potential_city_permit_reference":CANDIDATE,
        "cross_source_address_number_conflict":True,
        "same_project_as_city_permit_verified":False,
        "buyer_identity_verified":False,
        "owner_or_contact_names_persisted":False,
        "planned_dates_not_actual_construction":True,
        "source_resale_rights_verified":False,
    }

def validate(result:dict) -> bool:
    if not isinstance(result,dict):
        return False
    if result.get("status")==HOLD:
        return result==hold()
    keys={
        "status","state_project_id","source_url","source_response_sha256",
        "state_project_name_verified","state_project_registration_status",
        "state_project_type","state_registered_apartment_units",
        "state_planned_construction_start","state_planned_completion",
        "state_registered_estimate_usd","state_owner_organisation_field_present",
        "state_design_firm_field_present","potential_city_permit_reference",
        "cross_source_address_number_conflict",
        "same_project_as_city_permit_verified","buyer_identity_verified",
        "owner_or_contact_names_persisted","planned_dates_not_actual_construction",
        "source_resale_rights_verified",
    }
    if set(result)!=keys:
        return False
    fixed={
        "status":STATE,"state_project_id":ID,"source_url":SOURCE,
        "state_project_name_verified":True,
        "state_project_registration_status":"Project Registered",
        "state_project_type":"MULTIFAMILY_APARTMENTS",
        "state_registered_apartment_units":359,
        "potential_city_permit_reference":CANDIDATE,
        "cross_source_address_number_conflict":True,
        "same_project_as_city_permit_verified":False,
        "buyer_identity_verified":False,
        "owner_or_contact_names_persisted":False,
        "planned_dates_not_actual_construction":True,
        "source_resale_rights_verified":False,
        "state_owner_organisation_field_present":True,
        "state_design_firm_field_present":True,
    }
    try:
        a=datetime.fromisoformat(result["state_planned_construction_start"]).date()
        b=datetime.fromisoformat(result["state_planned_completion"]).date()
        v=result["state_registered_estimate_usd"]
    except (KeyError,TypeError,ValueError):
        return False
    return (
        all(result.get(k)==v for k,v in fixed.items())
        and bool(re.fullmatch(r"[0-9a-f]{64}",str(result.get("source_response_sha256",""))))
        and 2026<=a.year<=2035 and a<b and b.year<=2040
        and type(v) is int and 1000000<=v<=250000000
    )
