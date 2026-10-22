"""Read-only five real business sample from official San Francisco open data.

Only business DBA names, original location IDs and self-reported broad
NAICS are queried. A location row is not a distinct buyer; a missing website
is NOT evidence that a business has no website. No contact/address fields.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import re

SCHEMA = "empire.jev.sf_real_five_business_research_sample.v1"
DATASET = "g8m3-pdis"
DATASET_URL = "https://data.sfgov.org/Economy-and-Community/Registered-Business-Locations-San-Francisco/g8m3-pdis"
API = "https://data.sfgov.org/resource/g8m3-pdis.json"
LICENCE = "https://opendatacommons.org/licenses/pddl/1-0/"
# Closed, exactly verified names, no open-ended people/name enumeration.
NAMES = {
    "Lutz Plumbing Inc":("238220","https://lutzplumbingsf.com/","lutz plumbing"),
    "Anatra Fire Protection Inc.":("238220","https://anatra-fire.myshopify.com/","anatra fire protection"),
    "Vitality Remodeling LLC":("236118","https://vitality-remodeling.com/","vitality remodeling"),
    "J & K Pro Plumbing Inc":("238220",None,None),
    "Odonovan Plumbing Inc":("238220",None,None),
}
EXPECTED_KEYS = {
    "Lutz Plumbing Inc":"0161122-01-001-0161122",
    "Anatra Fire Protection Inc.":"1289321-10-211-1128845",
    "Vitality Remodeling LLC":"1404635-11-251-1176687",
    "J & K Pro Plumbing Inc":"1362209-05-241-1158835",
    "Odonovan Plumbing Inc":"0475345-01-001-0475345",
}
ALLOWED_FIELDS = {
    "uniqueid","dba_name","self_reported_naics_code","city","state",
    "location_end_date","dba_end_date","administratively_closed","data_as_of",
}


def _fetch_json(url:str,max_bytes:int)->Any:
    req=Request(url,headers={"User-Agent":"EmpireOS-Limited-Business-Registry-QA/1.0","Accept":"application/json"})
    with urlopen(req,timeout=10) as response:
        if response.status!=200:
            raise ValueError("official dataset HTTP status unexpected")
        raw=response.read(max_bytes+1)
        if len(raw)>max_bytes:
            raise ValueError("bounded registry query exceeded")
        return json.loads(raw)


def review_five_businesses(*,now:datetime,live_web_checks:bool=True,
                           observed_web:Mapping[str,Any]|None=None)->dict[str,Any]:
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("aware internal review clock required")
    if type(live_web_checks) is not bool or (live_web_checks and observed_web is not None):
        raise ValueError("live website requests and prior observations are mutually exclusive")
    if observed_web is not None:
        if (not isinstance(observed_web,Mapping)
            or observed_web.get("schema_version")!="empire.jev.first_party_site_manual_observations.v1"
            or observed_web.get("as_of_date")!=now.date().isoformat()
            or observed_web.get("source_method")!="bounded_independent_public_web_read_plus_server_https_get"
            or observed_web.get("contacts_collected")!=0
            or observed_web.get("outbound_sent")!=0
            or set(observed_web.get("website_results",{}))!={
                "Lutz Plumbing Inc","Anatra Fire Protection Inc.","Vitality Remodeling LLC"}):
            raise ValueError("untrusted exact manual site observation packet")
    where="city='San Francisco' AND ("+" OR ".join(
        "dba_name='"+name.replace("'","''")+"'"
        for name in sorted(NAMES)
    )+")"
    params={
        "$select":",".join(sorted(ALLOWED_FIELDS)),
        "$where":where,"$limit":20,"$order":"data_as_of DESC",
    }
    query=API+"?"+urlencode(params)
    records=_fetch_json(query,100000)
    if not isinstance(records,list) or not 5<=len(records)<=20:
        raise ValueError("expected original official location set missing")
    grouped=defaultdict(list)
    for record in records:
        if (not isinstance(record,dict)
            or not set(record).issubset(ALLOWED_FIELDS)
            or record.get("dba_name") not in NAMES
            or record.get("city")!="San Francisco"
            or record.get("state")!="CA"
            or not isinstance(record.get("uniqueid"),str)
            or not re.fullmatch(r"[0-9-]{15,35}",record["uniqueid"])
            or record.get("self_reported_naics_code") not in (NAMES[record["dba_name"]][0],None)
            or not isinstance(record.get("data_as_of"),str)
            or record["data_as_of"][:10]!=now.date().isoformat()):
            raise ValueError("registry source data outside limited authorized projection")
        grouped[record["dba_name"]].append(record)
    if set(grouped)!=set(NAMES):
        raise ValueError("five named businesses did not match original registry")
    result=[]
    for name,(naics,site,marker) in NAMES.items():
        locations=grouped[name]
        current=[r for r in locations if not r.get("dba_end_date")
                 and not r.get("location_end_date")
                 and r.get("administratively_closed") not in (True,"true")]
        keys={r["uniqueid"] for r in locations}
        anchored=[r for r in current if r["uniqueid"]==EXPECTED_KEYS[name]]
        if (len(keys)!=len(locations)
            or not current or len(anchored)!=1
            or anchored[0].get("self_reported_naics_code")!=naics):
            raise ValueError("missing or shifted official business location proof")
        state="NO_ATTRIBUTABLE_FIRST_PARTY_SITE_CONFIRMED"
        http_code=None
        original_site_checked=False
        if site and observed_web is not None:
            obs=observed_web["website_results"].get(name)
            if (not isinstance(obs,dict) or obs.get("website_url")!=site
                or obs.get("web_search_independent_company_identity") is not True
                or obs.get("status") not in (
                    "FIRST_PARTY_BRANDED_WEBSITE_OBSERVED",
                    "FIRST_PARTY_SITE_ORIGIN_HTTP_429_LATEST_RECHECK")
                or obs.get("live_get_brand_match_observed_before") is not True
                or obs.get("latest_http_observed")!=(429 if obs.get("status")==
                    "FIRST_PARTY_SITE_ORIGIN_HTTP_429_LATEST_RECHECK" else 200)):
                raise ValueError("unsupported or altered third-party site observation")
            state=obs["status"]
            http_code=429 if state=="FIRST_PARTY_SITE_ORIGIN_HTTP_429_LATEST_RECHECK" else 200
            original_site_checked=bool(obs.get("live_get_brand_match_observed_before"))
        if site and live_web_checks:
            parsed=urlparse(site)
            if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("untrusted direct corporate URL")
            try:
                req=Request(site,headers={"User-Agent":"EmpireOS-FirstParty-Website-QA/1.0",
                                          "Accept":"text/html"})
                with urlopen(req,timeout=8) as response:
                    final=urlparse(response.geturl())
                    data=response.read(200000).decode("utf8","ignore").lower()
                    http_code=response.status
                    if (final.scheme=="https" and final.hostname==parsed.hostname
                        and response.status==200
                        and "text/html" in response.headers.get("Content-Type","").lower()
                        and marker in data):
                        state="FIRST_PARTY_BRANDED_WEBSITE_OBSERVED"
                    else:
                        state="WEBSITE_FETCH_OR_BRAND_MATCH_INCONCLUSIVE"
                    original_site_checked=True
            except (HTTPError,URLError,OSError,TimeoutError,ValueError):
                state="WEBSITE_FETCH_OR_BRAND_MATCH_INCONCLUSIVE"
        result.append({
            "business_name":name,
            "registry_original_location_key":EXPECTED_KEYS[name],
            "registry_location_row_count":len(locations),
            "separate_business_entities_inferred_from_location_rows":1,
            "current_location_row_in_snapshot":True,
            "dataset_self_reported_naics":naics,
            "registry_latest_data_as_of":anchored[0]["data_as_of"][:10],
            "active_business_location_rows":len(current),
            "public_first_party_site":site,
            "first_party_site_review_status":state,
            "original_site_response_http":http_code,
            "original_site_checked_on_server":original_site_checked,
            "site_observation_from_pinned_evidence":observed_web is not None and site is not None,
            "site_absent_proven":False,
            "website_outdated_proven":False,
            "lawful_contact_or_marketing_eligibility_verified":False,
            "need_for_website_service_verified":False,
            "paid_buyer_acceptance_verified":False,
            "outreach_authorized":False,
        })
    return {
        "schema_version":SCHEMA,
        "status":"REAL_REGISTRY_BUSINESS_SAMPLE_INTERNAL_WEBSITE_RESEARCH_ONLY",
        "reviewed_at_utc":now.astimezone(timezone.utc).isoformat(),
        "source_dataset":DATASET_URL,
        "registry_source_api_host":"data.sfgov.org",
        "dataset_metadata_public_domain_license":LICENCE,
        "licence_for_source_business_rows_observed":True,
        "individuals_or_contacts_reuse_rights_verified":False,
        "official_registry_location_rows_seen":len(records),
        "unique_selected_businesses":len(result),
        "duplicate_or_ended_extra_location_rows":len(records)-len(result),
        "businesses":result,
        "first_party_sites_directly_confirmed":sum(x["first_party_site_review_status"]=="FIRST_PARTY_BRANDED_WEBSITE_OBSERVED" for x in result),
        "not_attributed_site_is_not_no_website":True,
        "actual_no_website_leads_verified":0,
        "buyer_purchase_intent_verified":0,
        "customer_accepted_leads":0,
        "website_status_sold_or_delivered":0,
        "crm_writes":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
