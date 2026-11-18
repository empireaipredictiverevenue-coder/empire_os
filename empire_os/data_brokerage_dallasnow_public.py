"""Bounded public DallasNow status verification inside existing brokerage owner.

No authenticated session, developer contact extraction or permit issuance
assumption. Only exact source-matched record number and current public status.
"""
from __future__ import annotations
from hashlib import sha256
from urllib.parse import urlparse, parse_qs, urljoin
import re

import requests
from bs4 import BeautifulSoup

HOME="https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building&TabName=Building"
HOST="aca-prod.accela.com"
REF=re.compile(r"COM-NEW-[0-9]{2}-[0-9]{6}\Z")
CAP_ID=re.compile(r"[A-Z0-9]{5}\Z")
# These five URLs were resolved through the anonymous official DallasNow
# search on 17 Nov 2026 and directly crosschecked against their page headers.
PUBLIC_CAP_IDS={
 "COM-NEW-26-000149":"012OP",
 "COM-NEW-26-000372":"02NQS",
 "COM-NEW-26-000370":"02NM5",
 "COM-NEW-26-000365":"02M9C",
 "COM-NEW-26-000298":"027AR",
}
STATUS_CLASSES={
 "Payment Due":"PAYMENT_PENDING_ISSUANCE_UNVERIFIED",
 "In Review":"UNDER_REVIEW_ISSUANCE_UNVERIFIED",
 "Inspection Phase":"INSPECTION_WORKFLOW_START_DATE_UNVERIFIED",
 "Issued":"RECORD_STATUS_ISSUED_DATE_UNVERIFIED",
 "Closed":"CLOSED_RECORD_NO_ACTIVE_OPPORTUNITY_ASSUMED",
}
SOURCE_STATUS_RE = r"Record\s+({ref})\s*:\s*Commercial New Construction Permit\s+Record Status:\s*([A-Za-z ]{{3,55}})\s+Expiration Date:"

def detail_url(ref:str, cap_id:str) -> str:
    if not REF.fullmatch(ref) or not CAP_ID.fullmatch(cap_id):
        raise ValueError("DALLASNOW_REF_OR_CAP_ID_INVALID")
    return ("https://aca-prod.accela.com/DALLASTX/Cap/CapDetail.aspx"
            f"?Module=Building&TabName=Building&capID1=REC{ref[8:10]}"
            f"&capID2=00000&capID3={cap_id}&agencyCode=DALLASTX"
            "&IsToShowInspection=")

def checked_url(value:str) -> str:
    url=urlparse(value)
    q=parse_qs(url.query)
    if (url.scheme!="https" or url.netloc!=HOST
        or url.path!="/DALLASTX/Cap/CapDetail.aspx"
        or q.get("Module")!=["Building"] or q.get("agencyCode")!=["DALLASTX"]
        or not CAP_ID.fullmatch(str(q.get("capID3",[""])[0]))):
        raise ValueError("DALLASNOW_NONOFFICIAL_DETAIL")
    return value

def public_detail(ref:str, *, url:str, session=None, timeout=7) -> dict:
    if not REF.fullmatch(ref) or not 2<=timeout<=9:
        raise ValueError("DALLASNOW_REF_OR_TIMEOUT_INVALID")
    url=checked_url(url)
    session=session or requests
    r=session.get(url,timeout=timeout,allow_redirects=False,
                  headers={"Accept":"text/html","User-Agent":"EmpireAI-Brokerage-PublicSourceQuality/1.0"})
    if (r.status_code!=200 or not r.headers.get("Content-Type","").startswith("text/html")
        or not 1000<len(r.content)<=650000):
        raise ValueError("DALLASNOW_PUBLIC_DETAIL_HELD")
    text=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
    match=re.search(SOURCE_STATUS_RE.format(ref=re.escape(ref)),text,re.I)
    if not match:
        raise ValueError("DALLASNOW_RECORD_REFERENCE_NOT_MATCHED")
    status=match.group(2).strip()
    if status not in STATUS_CLASSES:
        raise ValueError("DALLASNOW_UNKNOWN_STATUS_HOLD")
    return {
        "permit_reference":ref,
        "official_record_status":status,
        "record_status_interpretation":STATUS_CLASSES[status],
        "source_url":url,
        "source_response_sha256":sha256(r.content).hexdigest(),
        "official_record_status_independently_verified":True,
        "permit_original_issuance_date_verified":False,
        "record_is_a_verified_buyer":False,
        "outreach_approved":False,
    }

def public_search_url(ref:str, *, session=None, timeout=7) -> str:
    """Search the public anonymous form. No portal login, CAPTCHA or API bypass."""
    if not REF.fullmatch(ref) or not 2<=timeout<=9:
        raise ValueError("DALLASNOW_REF_OR_TIMEOUT_INVALID")
    session=session or requests.Session()
    r=session.get(HOME,timeout=timeout,allow_redirects=False,
                  headers={"Accept":"text/html","User-Agent":"EmpireAI-Brokerage-PublicSourceQuality/1.0"})
    if r.status_code!=200 or not 1000<len(r.content)<=650000:
        raise ValueError("DALLASNOW_PUBLIC_SEARCH_UNAVAILABLE")
    form=BeautifulSoup(r.text,"html.parser").find("form")
    if form is None:
        raise ValueError("DALLASNOW_SEARCH_FORM_ABSENT")
    data={}
    for node in form.select("input[name]"):
        typ=(node.get("type") or "").lower()
        if typ not in ("checkbox","radio","file","image","submit","button","password"):
            data[node["name"]]=node.get("value") or ""
    for node in form.select("select[name]"):
        option=node.select_one("option[selected]") or node.select_one("option")
        if option:
            data[node["name"]]=option.get("value") or ""
    if "__VIEWSTATE" not in data or len(data)>80:
        raise ValueError("DALLASNOW_PUBLIC_FORM_STRUCTURE_UNEXPECTED")
    data["ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber"]=ref
    data["__EVENTTARGET"]="ctl00$PlaceHolderMain$btnNewSearch"
    data["__EVENTARGUMENT"]=""
    result=session.post(HOME,data=data,timeout=timeout,allow_redirects=False,
                        headers={"Referer":HOME,"User-Agent":"EmpireAI-Brokerage-PublicSourceQuality/1.0"})
    link=result.headers.get("Location","")
    if (result.status_code!=302
        or not link.startswith("/DALLASTX/Cap/CapDetail.aspx?")):
        raise ValueError("DALLASNOW_PUBLIC_RECORD_SEARCH_HELD")
    return checked_url(urljoin(HOME,link))

def review_candidates(candidates:list[dict], *, session_factory=None,
                      max_records=5, max_unmapped=2, timeout=7) -> dict:
    if not 1<=max_records<=5 or not 0<=max_unmapped<=2 or not 2<=timeout<=9:
        raise ValueError("DALLASNOW_SOURCE_BUDGET_INVALID")
    if not isinstance(candidates,list) or len(candidates)>8:
        raise ValueError("DALLASNOW_SOURCE_CANDIDATES_UNBOUNDED")
    output=[]
    seen=set()
    unknown_attempts=0
    for row in candidates[:max_records]:
        ref=row.get("source_permit_reference") if isinstance(row,dict) else None
        if not isinstance(ref,str) or not REF.fullmatch(ref) or ref in seen:
            raise ValueError("DALLASNOW_UNTRUSTED_SOURCE_REFERENCE")
        seen.add(ref)
        cap=PUBLIC_CAP_IDS.get(ref)
        if cap:
            url=detail_url(ref,cap)
            session=(session_factory() if session_factory else requests.Session())
        elif unknown_attempts<max_unmapped:
            unknown_attempts+=1
            session=(session_factory() if session_factory else requests.Session())
            try:
                url=public_search_url(ref,session=session,timeout=timeout)
            except (ValueError,requests.RequestException):
                output.append({"permit_reference":ref,
                               "status":"OFFICIAL_RECORD_SEARCH_HELD",
                               "record_status_verified":False})
                continue
        else:
            output.append({"permit_reference":ref,
                           "status":"PENDING_NEXT_BOUNDED_OFFICIAL_LOOKUP",
                           "record_status_verified":False})
            continue
        try:
            proof=public_detail(ref,url=url,session=session,timeout=timeout)
            output.append(proof)
        except (ValueError,requests.RequestException):
            output.append({"permit_reference":ref,
                           "status":"OFFICIAL_PUBLIC_DETAIL_HELD",
                           "record_status_verified":False})
    accepted=[x for x in output if x.get("official_record_status_independently_verified") is True]
    canonical=[(x["permit_reference"],x["official_record_status"]) for x in accepted]
    status_hash=sha256(repr(sorted(canonical)).encode()).hexdigest()
    return {
        "status":"OFFICIAL_PUBLIC_RECORD_STATUS_REVIEW",
        "candidate_count":len(output),
        "verified_record_status_count":len(accepted),
        "unverified_status_count":len(output)-len(accepted),
        "source_lookup_budget":max_records,
        "unmapped_search_budget":max_unmapped,
        "record_status_fingerprint":status_hash,
        "record_status_counts":dict(sorted(__import__("collections").Counter(
            x["official_record_status"] for x in accepted).items())),
        "records":output,
        "all_record_statuses_currently_verified":len(output)>0 and len(accepted)==len(output),
        "actual_issuance_dates_verified":0,
        "customer_identity_inferred":False,
        "outbound_sent":False,
    }

def held_review(candidate_count:int) -> dict:
    if type(candidate_count) is not int or not 0<=candidate_count<=8:
        raise ValueError("DALLASNOW_HELD_COUNT_INVALID")
    return {
        "status":"OFFICIAL_DALLASNOW_CHECK_HELD",
        "source_candidates_unchecked":candidate_count,
        "verified_record_status_count":0,
        "record_status_fingerprint":sha256(b"no_verified_public_records").hexdigest(),
        "records":[],
        "actual_issuance_dates_verified":0,
        "customer_identity_inferred":False,
        "outbound_sent":False,
    }


def validate_review(value:dict, *, expected_refs:list[str]) -> bool:
    if not isinstance(value,dict) or not isinstance(expected_refs,list):
        return False
    if len(expected_refs)>8 or len(set(expected_refs))!=len(expected_refs):
        return False
    if not all(REF.fullmatch(x or "") for x in expected_refs):
        return False
    if value.get("status")=="OFFICIAL_DALLASNOW_CHECK_HELD":
        return (
            set(value)==set(held_review(0))
            and value.get("source_candidates_unchecked")==len(expected_refs)
            and value.get("verified_record_status_count")==0
            and value.get("records")==[]
            and value.get("actual_issuance_dates_verified")==0
            and value.get("customer_identity_inferred") is False
            and value.get("outbound_sent") is False
            and value.get("record_status_fingerprint")==held_review(0)["record_status_fingerprint"]
        )
    if value.get("status")!="OFFICIAL_PUBLIC_RECORD_STATUS_REVIEW":
        return False
    expected_keys={
        "status","candidate_count","verified_record_status_count",
        "unverified_status_count","source_lookup_budget",
        "unmapped_search_budget","record_status_fingerprint",
        "record_status_counts","records",
        "all_record_statuses_currently_verified",
        "actual_issuance_dates_verified","customer_identity_inferred","outbound_sent",
    }
    if set(value)!=expected_keys:
        return False
    records=value.get("records")
    if (not isinstance(records,list) or len(records)>5
        or value.get("candidate_count")!=len(records)
        or value.get("candidate_count")!=min(5,len(expected_refs))
        or value.get("source_lookup_budget") not in (1,2,3,4,5)
        or value.get("unmapped_search_budget") not in (0,1,2)
        or value.get("actual_issuance_dates_verified")!=0
        or value.get("customer_identity_inferred") is not False
        or value.get("outbound_sent") is not False):
        return False
    seen=[]
    accepted=[]
    for item in records:
        if not isinstance(item,dict):
            return False
        ref=item.get("permit_reference")
        if not isinstance(ref,str) or not REF.fullmatch(ref) or ref in seen:
            return False
        seen.append(ref)
        if item.get("official_record_status_independently_verified") is True:
            keys={
                "permit_reference","official_record_status",
                "record_status_interpretation","source_url",
                "source_response_sha256",
                "official_record_status_independently_verified",
                "permit_original_issuance_date_verified",
                "record_is_a_verified_buyer","outreach_approved",
            }
            state=item.get("official_record_status")
            if (set(item)!=keys or state not in STATUS_CLASSES
                or item.get("record_status_interpretation")!=STATUS_CLASSES[state]
                or item.get("permit_original_issuance_date_verified") is not False
                or item.get("record_is_a_verified_buyer") is not False
                or item.get("outreach_approved") is not False
                or not re.fullmatch(r"[0-9a-f]{64}",str(item.get("source_response_sha256","")))):
                return False
            try:
                checked_url(item["source_url"])
            except (ValueError,TypeError):
                return False
            accepted.append((ref,state))
        else:
            if (set(item)!={"permit_reference","status","record_status_verified"}
                or item.get("record_status_verified") is not False
                or item.get("status") not in (
                    "OFFICIAL_RECORD_SEARCH_HELD","OFFICIAL_PUBLIC_DETAIL_HELD",
                    "PENDING_NEXT_BOUNDED_OFFICIAL_LOOKUP")):
                return False
    if seen != expected_refs[:len(records)]:
        return False
    if (value.get("verified_record_status_count")!=len(accepted)
        or value.get("unverified_status_count")!=len(records)-len(accepted)
        or value.get("all_record_statuses_currently_verified") is not (
            len(records)>0 and len(accepted)==len(records))
        or value.get("record_status_counts") != dict(sorted(__import__("collections").Counter(
            status for _,status in accepted).items()))
        or value.get("record_status_fingerprint") != sha256(
            repr(sorted(accepted)).encode()).hexdigest()):
        return False
    return True
