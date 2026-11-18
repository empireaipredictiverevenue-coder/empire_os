"""Scientific, institutional and professional research evidence in original Data Brokerage.

Single-owner adapter: source mining heartbeat, no duplicate database, worker,
scheduler, send route or product catalogue. A known small first-party cohort
tests research metadata acquisition and safe, typed change detection.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import json
import os
import re
import tempfile
import csv

from empire_os.data_brokerage_scientific_source_contracts import scientific_source_contracts

SOURCE_CONTRACTS = scientific_source_contracts()

SCHEMA = "empire.data_brokerage.multi_niche_scientific_evidence.v1"
STATE = Path("runtime/data_brokerage/multi_niche_scientific_evidence_latest.json")
CANONICAL = Path("/srv/empire_os")
MIN_INTERVAL = timedelta(hours=24)
MAX_RESPONSE = 280_000
MAX_RECORDS = 16
SOURCES = {
    "ror": {
        "url": SOURCE_CONTRACTS["global_ror_research_organisations"].url,
        "entity_kind": "research_organisation",
        "source_rights": SOURCE_CONTRACTS["global_ror_research_organisations"].licence,
        "market_lanes": ("scientific_research", "biotech", "healthcare", "education"),
        "owner": "Research Organization Registry",
    },
    "crossref": {
        "url": SOURCE_CONTRACTS["global_crossref_research_publications"].url,
        "entity_kind": "research_work",
        "source_rights": SOURCE_CONTRACTS["global_crossref_research_publications"].licence,
        "market_lanes": ("scientific_research", "biotech", "technology"),
        "owner": "Crossref",
    },
    "clinicaltrials": {
        "url": SOURCE_CONTRACTS["us_clinicaltrials_study_metadata"].url,
        "entity_kind": "clinical_study",
        "source_rights": SOURCE_CONTRACTS["us_clinicaltrials_study_metadata"].licence,
        "market_lanes": ("healthcare", "biotech", "clinical_research"),
        "owner": "ClinicalTrials.gov",
    },
    "nih": {
        "url": SOURCE_CONTRACTS["us_nih_reporter_grants"].url,
        "entity_kind": "research_grant",
        "source_rights": SOURCE_CONTRACTS["us_nih_reporter_grants"].licence,
        "market_lanes": ("scientific_research", "biotech", "healthcare"),
        "owner": "NIH RePORTER",
    },
    "openalex": {
        "url": SOURCE_CONTRACTS["global_openalex_research_graph"].url,
        "entity_kind": "research_work",
        "source_rights": SOURCE_CONTRACTS["global_openalex_research_graph"].licence,
        "market_lanes": ("scientific_research", "education", "technology"),
        "owner": "OpenAlex",
    },
}
TYPED_DOMAINS = {
    "research_organisation", "research_work", "clinical_study",
    "research_professional", "company", "research_grant",
}
MARKET_LANES = (
    "scientific_research", "biotech", "healthcare", "clinical_research",
    "education", "technology", "investment", "legal", "insurance",
    "energy", "construction", "property", "procurement",
)
ENTITY_CHANGE_FIELDS = {
    "research_organisation": ("name", "status", "types"),
    "research_work": ("title", "publication_date", "work_type"),
    "clinical_study": ("brief_title", "overall_status", "last_update_post_date", "lead_sponsor"),
    "research_professional": ("display_name", "source_work_id", "authorship_position"),
    "company": ("issuer_reported_name", "sec_industry", "qualification_tier"),
    "research_grant": (
        "project_number", "project_title", "fiscal_year",
        "issuer_reported_award_amount_usd", "project_start_date",
    ),
}
MAX_LABEL = 240
ROR_RE = re.compile(r"https://ror\.org/[a-z0-9]{9}$")
NCT_RE = re.compile(r"NCT[0-9]{8}$")
OPENALEX_WORK_RE = re.compile(r"https://openalex\.org/W[0-9]{6,14}$")
OPENALEX_AUTHOR_RE = re.compile(r"https://openalex\.org/A[0-9]{6,14}$")
DOI_RE = re.compile(r"10\.[0-9]{4,9}/[^\s<>]{1,145}$")
CIK_RE = re.compile(r"[1-9][0-9]{0,9}$")
NIH_PROJECT_RE = re.compile(r"[0-9A-Z-]{6,35}$")
NIH_PROJECT_CRITERIA = {
    "criteria": {"fiscal_years": [2025]},
    "offset": 0, "limit": 1,
    "include_fields": [
        "ApplId", "ProjectNum", "ProjectTitle", "FiscalYear",
        "AwardAmount", "ProjectStartDate", "ProjectDetailUrl",
    ],
}
NO_AUTHORITY = {
    "sales_outreach_authorized": False,
    "customer_distribution_authorized": False,
    "automatic_resale_authorized": False,
    "crm_writes": False,
    "payments_authorized": False,
    "external_submissions": False,
}


def digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scientific_original_evidence_requires_aware_time")
    return value.astimezone(timezone.utc)


def _safe_text(value: Any, *, max_len: int = MAX_LABEL) -> str | None:
    if type(value) is not str:
        return None
    clean = " ".join(value.strip().split())
    if not clean or len(clean) > max_len or any(ord(c)<32 for c in clean):
        return None
    return clean


def _single_text(value: Any, *, max_len: int = MAX_LABEL) -> str | None:
    if isinstance(value, list):
        return _safe_text(value[0],max_len=max_len) if value else None
    return _safe_text(value,max_len=max_len)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_official_scientific_metadata(source_id: str) -> Mapping[str, Any]:
    """One static approved metadata endpoint; no search queries or PII fields."""
    if source_id not in SOURCES:
        raise ValueError("unregistered_scientific_source")
    url = SOURCES[source_id]["url"]
    headers = {
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Data-Brokerage-Research/1.0 (empire-ai.co.uk)",
    }
    if source_id == "nih":
        # Single, static, bounded fiscal-year metadata query, never
        # investigator names/emails or automatic opportunity searches.
        headers["Content-Type"] = "application/json"
        request = Request(
            url, headers=headers,
            data=json.dumps(NIH_PROJECT_CRITERIA,sort_keys=True).encode("utf-8"),
            method="POST",
        )
    else:
        request = Request(url,headers=headers,method="GET")
    with build_opener(_NoRedirect).open(request, timeout=7) as response:
        if response.status!=200 or response.geturl()!=url or not response.headers.get(
            "Content-Type", ""
        ).lower().startswith("application/json"):
            raise ValueError("scientific_first_party_source_proof_not_verified")
        raw=response.read(MAX_RESPONSE+1)
    if len(raw)>MAX_RESPONSE or not raw:
        raise ValueError("scientific_public_json_over_limit")
    document=json.loads(raw)
    if not isinstance(document, Mapping):
        raise ValueError("scientific_public_response_not_an_object")
    return document


def _make_record(*, source_id: str, entity_id: str, kind: str,
                 fields: dict[str, Any], proof_url: str,
                 source_updated: str | None = None) -> dict[str, Any]:
    if (source_id not in SOURCES and source_id!="existing_sec_formd"
            or kind not in TYPED_DOMAINS or
            set(fields)!=set(ENTITY_CHANGE_FIELDS[kind])):
        raise ValueError("unreviewed_scientific_source_or_entity_field")
    for key,v in fields.items():
        if v is not None and not (
            isinstance(v,str) and 0<len(v)<=MAX_LABEL
            or isinstance(v,list) and len(v)<=6
            and all(type(x) is str and len(x)<=50 for x in v)
        ):
            raise ValueError("unbounded_scientific_source_field")
    if not proof_url.startswith("https://") or len(proof_url)>350:
        raise ValueError("invalid_first_party_science_proof")
    if not entity_id or len(entity_id)>190:
        raise ValueError("invalid_scientific_entity_identity")
    return {
        "entity_id": entity_id,
        "entity_kind": kind,
        "source_id": source_id,
        "source_original_url": proof_url,
        "source_reported_updated": source_updated,
        "fields": fields,
        "field_content_sha256": digest(fields),
        "identity_status": "SOURCE_IDENTIFIER_ONLY_NO_UNVERIFIED_CROSS_SOURCE_JOIN",
        "source_data_not_independent_fact_confirmation": True,
        "contact_address_extracted": False,
        "customer_buying_intent_verified": False,
    }


def normalize_first_party_science(source_id: str, doc: Mapping[str,Any]) -> list[dict[str,Any]]:
    if source_id not in SOURCES or not isinstance(doc,Mapping):
        raise ValueError("invalid_first_party_scientific_document")
    url=SOURCES[source_id]["url"]
    if source_id=="nih":
        results=doc.get("results")
        if not isinstance(results,list) or len(results)!=1:
            raise ValueError("nih_bounded_project_result_missing")
        record=results[0]
        if not isinstance(record,Mapping):
            raise ValueError("nih_project_not_public_record")
        app_id=record.get("appl_id")
        num=_safe_text(record.get("project_num"),max_len=45)
        title=_safe_text(record.get("project_title"))
        fiscal=record.get("fiscal_year")
        amount=record.get("award_amount")
        start=_safe_text(record.get("project_start_date"),max_len=45)
        if (type(app_id) is not int or not 0<app_id<10**12
                or num is None or NIH_PROJECT_RE.fullmatch(num) is None
                or title is None or type(fiscal) is not int or fiscal!=2025
                or type(amount) is not int or amount<0 or amount>10**11):
            raise ValueError("nih_original_project_identifier_or_field_invalid")
        proof="https://reporter.nih.gov/project-details/"+str(app_id)
        claimed=record.get("project_detail_url")
        if claimed is not None and claimed!=proof:
            raise ValueError("nih_source_project_url_mismatch")
        return [_make_record(
            source_id=source_id,kind="research_grant",
            entity_id="nih_appl:"+str(app_id),
            fields={
                "project_number":num, "project_title":title,
                "fiscal_year":str(fiscal),
                "issuer_reported_award_amount_usd":str(amount),
                "project_start_date":start,
            },proof_url=proof)]
    if source_id=="ror":
        ident=_safe_text(doc.get("id"))
        display=next(
            (_safe_text(n.get("value")) for n in doc.get("names",[])[:20]
             if isinstance(n,Mapping) and "ror_display" in (n.get("types") or [])), None
        )
        typ=doc.get("types")
        if not ident or not ROR_RE.fullmatch(ident) or ident!=url.replace(
            "https://api.ror.org/v2/organizations/", "https://ror.org/"
        ) or not display or not isinstance(typ,list):
            raise ValueError("ror_identity_or_official_name_unverified")
        types=sorted(set(x for x in typ if type(x) is str and 0<len(x)<=50))[:6]
        status=_safe_text(doc.get("status"))
        return [_make_record(source_id=source_id,kind="research_organisation",
            entity_id="ror:"+ident.rsplit("/",1)[-1],
            fields={"name":display,"status":status,"types":types},proof_url=ident,
            source_updated=_safe_text(doc.get("updated"),max_len=45))]
    if source_id=="crossref":
        msg=doc.get("message")
        if not isinstance(msg,Mapping):
            raise ValueError("crossref_message_missing")
        doi=_safe_text(msg.get("DOI"),max_len=170)
        if (not doi or not DOI_RE.fullmatch(doi)
                or doi.casefold()!=url.rsplit("/works/",1)[-1].casefold()):
            raise ValueError("crossref_doi_source_mismatch")
        title=_single_text(msg.get("title"))
        if not title: raise ValueError("crossref_publication_title_missing")
        date=msg.get("published") or {}
        parts=date.get("date-parts") if isinstance(date,Mapping) else None
        published="-".join(str(v) if i==0 else f"{v:02d}" for i,v in enumerate(parts[0][:3])) if (
            isinstance(parts,list) and parts and isinstance(parts[0],list)
            and all(type(x) is int and 0<x<10000 for x in parts[0][:3])
        ) else None
        return [_make_record(source_id=source_id,kind="research_work",
            entity_id="doi:"+doi.casefold(),
            fields={"title":title,"publication_date":published,
                    "work_type":_safe_text(msg.get("type"))},
            proof_url="https://doi.org/"+doi,
            source_updated=None)]
    if source_id=="clinicaltrials":
        protocol=doc.get("protocolSection")
        if not isinstance(protocol,Mapping):raise ValueError("trial_protocol_missing")
        ident=protocol.get("identificationModule") or {}
        status=protocol.get("statusModule") or {}
        sponsor=protocol.get("sponsorCollaboratorsModule") or {}
        nct=_safe_text(ident.get("nctId"))
        if nct!="NCT02993146" or not NCT_RE.fullmatch(nct):
            raise ValueError("trial_id_not_same_original_source")
        title=_safe_text(ident.get("briefTitle"))
        if not title:raise ValueError("trial_source_title_missing")
        upd=status.get("studyFirstPostDateStruct") or {}
        posted=status.get("studyFirstPostDateStruct") or {}
        last=status.get("lastUpdatePostDateStruct") or {}
        last_date=_safe_text(last.get("date"))
        lead=sponsor.get("leadSponsor") or {}
        return [_make_record(source_id=source_id,kind="clinical_study",
            entity_id="nct:"+nct,
            fields={"brief_title":title,"overall_status":_safe_text(status.get("overallStatus")),
                    "last_update_post_date":last_date,
                    "lead_sponsor":_safe_text(lead.get("name"))},
            proof_url="https://clinicaltrials.gov/study/"+nct,
            source_updated=last_date)]
    if source_id=="openalex":
        ident=_safe_text(doc.get("id"))
        if not ident or not OPENALEX_WORK_RE.fullmatch(ident) or ident!=url.replace(
            "https://api.openalex.org/works/","https://openalex.org/"
        ):
            raise ValueError("openalex_work_identity_unverified")
        title=_safe_text(doc.get("title"))
        if not title:raise ValueError("openalex_work_title_missing")
        records=[_make_record(source_id=source_id,kind="research_work",
            entity_id="openalex_work:"+ident.rsplit("/",1)[-1],
            fields={"title":title,
                    "publication_date":_safe_text(doc.get("publication_date")),
                    "work_type":_safe_text(doc.get("type"))},
            proof_url=ident,source_updated=_safe_text(doc.get("updated_date")))]
        # Source authorship is NOT proof of employment, current academic
        # qualification, a contact email or verified ORCID identity.
        authors=doc.get("authorships") or []
        if not isinstance(authors,list):authors=[]
        seen=set()
        for item in authors[:8]:
            if not isinstance(item,Mapping):continue
            author=item.get("author") or {}
            if not isinstance(author,Mapping):continue
            author_id=_safe_text(author.get("id"))
            name=_safe_text(author.get("display_name"))
            if (not author_id or not OPENALEX_AUTHOR_RE.fullmatch(author_id)
                    or not name or author_id in seen):
                continue
            seen.add(author_id)
            records.append(_make_record(
                source_id=source_id,kind="research_professional",
                entity_id="openalex_author:"+author_id.rsplit("/",1)[-1],
                fields={"display_name":name,
                        "source_work_id":records[0]["entity_id"],
                        "authorship_position":_safe_text(item.get("author_position"))},
                proof_url=author_id))
            if len(records)>=3:break
        return records
    raise ValueError("unknown_scientific_source_adapter")


def _record_sec_company(review: Mapping[str,Any]) -> list[dict[str,Any]]:
    """Reuses existing verified signed SEC review; no new filings are fetched."""
    if not isinstance(review,Mapping) or review.get("status")!="SEC_FORMD_ORIGINAL_ISSUER_QUALIFICATION_REVIEW":
        return []
    result=[]
    for item in (review.get("qualified_research_candidates") or [])[:6]:
        if not isinstance(item,Mapping):continue
        cik=str(item.get("cik") or "").strip()
        name=_safe_text(item.get("sec_issuer_name"))
        sec_url=_safe_text(item.get("sec_primary_doc_url"),max_len=350)
        if (not CIK_RE.fullmatch(cik) or not name or not sec_url
                or not sec_url.startswith("https://www.sec.gov/Archives/edgar/data/"+cik+"/")):
            continue
        sector=_safe_text(item.get("sec_industry_group"))
        tier=_safe_text(item.get("qualification_tier"))
        result.append(_make_record(
            source_id="existing_sec_formd",kind="company",
            entity_id="sec_cik:"+cik,proof_url=sec_url,
            fields={"issuer_reported_name":name,"sec_industry":sector,
                    "qualification_tier":tier},
        ))
    return result[:3]


def compare_source_snapshots(prior: Mapping[str, Any]|None,
                             current: list[dict[str,Any]], *,
                             current_observed: datetime) -> dict[str,Any]:
    """Source-reported metadata changed vs immutable prior observation.

    Never conflate a missing sampled entity with a disappearing organisation,
    an updated paper with a new discovery, or a trial status with actual
    clinical efficacy or recruiting permission.
    """
    stamp=aware(current_observed)
    if not isinstance(current,list) or len(current)>MAX_RECORDS:
        raise ValueError("unbounded_science_change_comparison")
    if prior is None:
        return {
            "status":"BASELINE_FIRST_OBSERVATION_NOT_A_CHANGE",
            "matched_count":0,"changed_count":0,
            "changes":[],"newly_sampled_not_new_entities":[],
            "missing_from_sample_not_deleted_entities":[],
            "source_records_reobserved":False,
            "automatic_sales_claims":False,
        }
    if prior.get("schema_version")!=SCHEMA or not isinstance(prior.get("records"),list):
        raise ValueError("old_scientific_source_receipt_contract_invalid")
    previous_stamp=datetime.fromisoformat(str(prior["observed_at"]))
    if stamp<=aware(previous_stamp):
        raise ValueError("scientific_snapshot_replay_or_nonmonotonic_time")
    prev={x["entity_id"]:x for x in prior["records"] if isinstance(x,Mapping)}
    cur={x["entity_id"]:x for x in current}
    if len(prev)!=len(prior["records"]) or len(cur)!=len(current):
        raise ValueError("duplicate_entity_ids_not_comparable")
    shared=sorted(set(prev)&set(cur))
    delta=[]
    for entity_id in shared:
        a,b=prev[entity_id],cur[entity_id]
        if a["entity_kind"]!=b["entity_kind"] or a["source_id"]!=b["source_id"]:
            raise ValueError("cross_source_identity_type_conflict")
        kind=b["entity_kind"]
        fields={}
        for key in ENTITY_CHANGE_FIELDS[kind]:
            if a["fields"][key]!=b["fields"][key]:
                fields[key]={"before":a["fields"][key],
                             "after":b["fields"][key]}
        if fields:
            delta.append({
                "entity_id":entity_id,"entity_kind":kind,
                "source_id":b["source_id"],
                "original_source_url":b["source_original_url"],
                "before_source_observed_at":prior["observed_at"],
                "after_source_observed_at":stamp.isoformat(),
                "source_metadata_changes":fields,
                "event_class":"SOURCE_REPORTED_METADATA_CHANGE_NOT_CAUSAL_OUTCOME",
                "independently_verified_real_world_event":False,
                "verified_buyer_signal":False,
                "contact_permission":False,
            })
    return {
        "status":"SOURCE_SNAPSHOT_COMPARISON_RESEARCH_ONLY",
        "matched_count":len(shared),"changed_count":len(delta),
        "changes":delta,
        "newly_sampled_not_new_entities":sorted(set(cur)-set(prev)),
        "missing_from_sample_not_deleted_entities":sorted(set(prev)-set(cur)),
        "source_records_reobserved":True,
        "automatic_sales_claims":False,
    }


def _read_previous(path: Path, *, now: datetime) -> dict[str,Any]|None:
    if path.is_symlink():
        raise ValueError("unsafe_scientific_receipt_symlink")
    if not path.exists():return None
    if not path.is_file() or not 0<path.stat().st_size<=100000:
        raise ValueError("scientific_source_receipt_size_invalid")
    obj=json.loads(path.read_text())
    if not isinstance(obj,dict) or obj.get("schema_version")!=SCHEMA:
        raise ValueError("scientific_source_schema_mismatch")
    body=dict(obj);signed=body.pop("integrity_sha256",None)
    if signed!=digest(body) or not isinstance(obj.get("records"),list):
        raise ValueError("scientific_source_receipt_integrity_mismatch")
    sampled=aware(datetime.fromisoformat(obj["observed_at"]))
    if sampled>now+timedelta(minutes=5):
        raise ValueError("scientific_source_receipt_future_timestamp")
    return obj


def _save_private(path: Path, data: Mapping[str,Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("unsafe_scientific_receipt_target")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.parent.chmod(0o700)
    file_descriptor,temp=tempfile.mkstemp(dir=path.parent,prefix=".scientific_evidence_",suffix=".tmp")
    try:
        with os.fdopen(file_descriptor,"w") as out:
            json.dump(data,out,sort_keys=True,ensure_ascii=False,allow_nan=False)
            out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def run_original_broker_scientific_evidence(
    root: Path, *, now: datetime|None=None,
    fetch: Callable[[str],Mapping[str,Any]]=fetch_official_scientific_metadata,
    persist: bool=True,
) -> dict[str,Any]:
    """Original brokerage owner call under existing source mining lock."""
    root=Path(root).resolve()
    if root!=CANONICAL:
        return {"status":"NONCANONICAL_NO_SCIENCE_NETWORK","external_requests":0,
                "customer_distribution_authorized":False}
    current=aware(now or datetime.now(timezone.utc))
    dest=root/STATE
    previous=_read_previous(dest,now=current)
    if not persist:
        return {"status":"READ_ONLY_SCIENCE_STATE",
                "previous_observed_at":previous["observed_at"] if previous else None,
                "external_requests":0,"customer_distribution_authorized":False}
    # The original brokerage owner runs this under its existing lock. The
    # official CQC CSV has an independent seven-day refresh window. It is
    # checked before the science cohort's 24-hour freshness short-circuit,
    # avoiding a second scheduler or duplicate source acquisition owner.
    try:
        from empire_os.data_brokerage_cqc_directory_evidence import (
            run_existing_broker_cqc_directory,
        )
        care_directory = run_existing_broker_cqc_directory(
            root, now=current, persist=True,
        )
    except (OSError, ValueError, TypeError, TimeoutError, KeyError,
            UnicodeError, RuntimeError, ImportError, csv.Error) as exc:
        care_directory = {
            "status":"CQC_ORIGINAL_SOURCE_EVIDENCE_HELD",
            "error_class":type(exc).__name__,
            "external_requests":"UNCONFIRMED_BOUNDED",
            "customer_distribution_authorized":False,
        }
    if previous:
        old_at=aware(datetime.fromisoformat(previous["observed_at"]))
        # A genuinely new original source contract warrants one evidence
        # baseline expansion even during the normal 24h refresh window.
        # The new source is thereafter subject to the same cooldown.
        new_source_scope = not set(SOURCES).issubset(
            set(previous.get("source_ids_attempted") or [])
        )
        if current-old_at<MIN_INTERVAL and not new_source_scope:
            return {"status":"EXISTING_SCIENTIFIC_EVIDENCE_FRESH",
                    "previous_observed_at":previous["observed_at"],
                    "source_records":len(previous["records"]),
                    "scientific_metadata_changes":previous["change_review"]["changed_count"],
                    "external_requests":0,"customer_distribution_authorized":False,
                    "cqc_regulated_care":care_directory}
    records: list[dict[str,Any]]=[]
    failures=[]
    for source in SOURCES:
        try:
            doc=fetch(source)
            row=normalize_first_party_science(source,doc)
            if len(records)+len(row)>MAX_RECORDS:
                raise ValueError("scientific_record_enrichment_cap")
            records.extend(row)
        except (HTTPError,URLError,OSError,ValueError,TypeError,KeyError,TimeoutError,OverflowError) as exc:
            failures.append({"source":source,"error_class":type(exc).__name__})
    # Independent existing SEC receipt is bound to its original source
    # signature; no new SEC request and no invented legal company join.
    try:
        from empire_os.search_fabric.sec_formd_source_quality_v1 import digest as sec_digest
        sec_path=root/"runtime/search_fabric_evidence/sec_formd_company_review_latest.json"
        if sec_path.is_symlink() or not sec_path.is_file():raise ValueError("sec_receipt_missing")
        source=json.loads(sec_path.read_text())
        signed=dict(source);check=signed.pop("integrity_sha256",None)
        if sec_digest(signed)!=check:raise ValueError("sec_company_source_signature_invalid")
        records.extend(_record_sec_company(source))
    except (OSError,ValueError,TypeError,KeyError,ImportError) as exc:
        failures.append({"source":"existing_sec_formd","error_class":type(exc).__name__})
    if len(records)>MAX_RECORDS:
        raise ValueError("cross_niche_brokerage_scope_exceeded")
    if len({r["entity_id"] for r in records})!=len(records):
        raise ValueError("cross_source_duplicate_entity_identifier")
    records.sort(key=lambda x:x["entity_id"])
    comparison=compare_source_snapshots(previous,records,current_observed=current)
    document={
        "schema_version":SCHEMA,
        "status":(
            "RESEARCH_MULTI_NICHE_SOURCE_BASELINE_VERIFIED"
            if not failures and previous is None
            else "RESEARCH_MULTI_NICHE_SOURCE_RECHECK_PARTIAL"
            if failures else "RESEARCH_MULTI_NICHE_SOURCE_RECHECK_VERIFIED"
        ),
        "observed_at":current.isoformat(),
        "owner":"EXISTING_DATA_BROKERAGE_SOURCE_MINING",
        "source_ids_attempted":list(SOURCES)+["existing_sec_formd"],
        "source_api_attempts":len(SOURCES),
        "source_api_expected_max_requests":len(SOURCES),
        "record_count":len(records),
        "entity_type_counts":{kind:sum(r["entity_kind"]==kind for r in records)
                              for kind in sorted(TYPED_DOMAINS)},
        "sector_lanes_supported":list(MARKET_LANES),
        "source_failures":failures,
        "source_rights":{k:{"scope":v["source_rights"],
                           "customer_licence_cleared":False}
                         for k,v in SOURCES.items()},
        "source_data_recency":"ONE_BOUNDED_ORIGINAL_SAMPLE_NOT_GLOBAL_COVERAGE",
        "research_professional_affiliation_verified":False,
        "trial_recruitment_and_efficacy_independently_verified":False,
        "original_scientific_commercial_buyers_verified":0,
        "records":records,
        "change_review":comparison,
        **NO_AUTHORITY,
    }
    document["integrity_sha256"]=digest(document)
    _save_private(dest,document)
    return {
        "status":document["status"],
        "observed_at":document["observed_at"],
        "source_records":len(records),
        "entity_type_counts":document["entity_type_counts"],
        "scientific_metadata_changes":comparison["changed_count"],
        "first_party_sources_failed":[x["source"] for x in failures],
        "external_requests_upper_bound":len(SOURCES),
        "receipt_sha256":document["integrity_sha256"],
        "customer_distribution_authorized":False,
        "outbound_sent":False,
        "execution_authority":"none",
        "cqc_regulated_care":care_directory,
    }
