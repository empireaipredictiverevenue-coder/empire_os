"""Only verified DOB NOW source-status columns may alter a previously seen permit.

In-place change capture belongs to the existing signal inbox file lock; never
claims new buyer/owner/property identity or imports contact fields.
"""
from __future__ import annotations
from datetime import date
from typing import Mapping
import re

from empire_os.lead_sources.nyc_dobnow import DATASET_PAGE, JOB

FIELDS = ("filing_date", "first_permit_date", "issued_date", "permit_status",
          "filing_reason", "work_type", "borough", "bin", "bbl",
          "solar_work_type", "general_construction_work_type")
MAX_REVISIONS = 12


def _date(v):
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _safe(raw):
    if not isinstance(raw, Mapping): return {}
    clean = {}
    types = raw.get("work_types")
    if (isinstance(types, list) and 1 <= len(types) <= 40
            and all(isinstance(t,str) and
                    re.fullmatch(r"[A-Za-z0-9_ -]{1,60}",t) for t in types)):
        clean["work_types"] = sorted(set(types))
    for key in FIELDS:
        val = raw.get(key)
        if key in ("filing_date", "first_permit_date", "issued_date"):
            if _date(val): clean[key] = val
        elif key in ("solar_work_type", "general_construction_work_type"):
            if type(val) is bool: clean[key] = val
        elif key == "bin":
            if isinstance(val,str) and re.fullmatch(r"\d{7}",val): clean[key]=val
        elif key == "bbl":
            if isinstance(val,str) and re.fullmatch(r"\d{10}",val): clean[key]=val
        elif key in ("permit_status", "filing_reason", "work_type", "borough"):
            if isinstance(val,str) and re.fullmatch(r"[A-Za-z0-9_ -]{1,60}",val): clean[key]=val
    return clean


def _trusted(row):
    if row.get("source")!="permits_nyc_dobnow" or row.get("url")!=DATASET_PAGE:
        return ""
    raw=row.get("raw")
    if not isinstance(raw,Mapping):return ""
    job=raw.get("job_filing_number")
    return job if isinstance(job,str) and JOB.fullmatch(job) else ""


def trusted_dobnow_match(existing, incoming):
    first,second=_trusted(existing),_trusted(incoming)
    return bool(first and first==second)


def refresh_dobnow_event(existing, incoming, *, observed_at):
    result={"event_revision_added":False}
    if not trusted_dobnow_match(existing,incoming):
        return result
    old=existing.get("raw")
    new=incoming.get("raw")
    if not isinstance(old,dict) or not isinstance(new,Mapping):
        return result
    new_fields=_safe(new)
    old_fields=_safe(old)
    if not new_fields or not old_fields:
        return result
    # A later fetch is not proof of a newer application or issuance event.
    # Reject any attempt to rewind the oldest retained official event date.
    if any(_date(new_fields.get(f)) and _date(old_fields.get(f)) and
           _date(new_fields[f])<_date(old_fields[f])
           for f in ("filing_date","first_permit_date","issued_date")):
        return result
    changes={k:{"previous":old_fields.get(k),"current":v}
             for k,v in new_fields.items() if old_fields.get(k)!=v}
    if not changes:
        return result
    history=existing.get("source_event_revisions")
    if not isinstance(history,list):history=[]
    history.append({
        "job_filing_number":_trusted(existing),
        "observed_at":observed_at,
        "changed_event_fields":changes,
        "source_event_truth":"OFFICIAL_DATA_COLUMN_UPDATE_NOT_NEW_PHYSICAL_PROJECT",
        "company_or_buyer_verified":False,
        "outbound_authorized":False
    })
    existing["source_event_revisions"]=history[-MAX_REVISIONS:]
    old.update(new_fields)
    existing["last_material_source_event_at"]=observed_at
    existing["source_event_revision_count"]=int(existing.get("source_event_revision_count") or 0)+1
    result["event_revision_added"]=True
    return result
