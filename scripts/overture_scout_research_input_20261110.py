#!/usr/bin/env python3
"""Original Buyer Scout: observe signed existing Overture first-party research.

No SkillForge auto execution. No live source provider calls. Original source
proof is manually curated, exact digest pinned, aged and fail-closed.
Novelty to canonical CRM is UNKNOWN and never changed to clear.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import hashlib,ipaddress,json,re
from pathlib import Path
from typing import Any,Mapping
from urllib.parse import urlsplit

ROOT=Path("/srv/empire_os")
SOURCE=Path("/home/ubuntu/empire_research/search_fabric_sources_20261110/overture_dallas_per_source_reconciled_20261110.json")
SOURCE_SHA="d209806171b445818ffaa465619e7648a79e1ade7e9f6071c4aabd79852e78d8"
INTAKE_SHA="f93bf53b9aa463bf564f9c6d14c373d72ee493c0a4e1e69b8a0a54111572b4bf"
INTAKE_RELATIVE="runtime/buyer_acquisition/overture_first_party_research_source_20261110.json"
PROSPECT_DUPLICATE_RELATIVE="runtime/search_fabric_evidence/overture_original_prospect_domain_check_20261110.json"
PROSPECT_DUPLICATE_SHA="eac8540fa11507b87a830242fb588c479f0b0563c7b5abcc7d8cc175ed7f3d9d"
PROSPECT_DUPLICATE_SCHEMA="empire.search_fabric.original_prospect_overture_domain_check.v1"
INTAKE_SCHEMA="empire.buyer_scout.overture_first_party_research.v1"
REVIEW_SCHEMA="empire.search_fabric.overture_licensed_first_party_research.v1"
MAX_AGE=timedelta(days=7)
class Held(ValueError):pass

def require(value:bool,message:str):
    if not value:raise Held(message)
def sha(path:Path)->str:
    require(path.is_file() and not path.is_symlink(),"INPUT_NOT_REGULAR_FILE")
    return hashlib.sha256(path.read_bytes()).hexdigest()
def domain(value:str)->str:
    if not isinstance(value,str):return ""
    try:
        parsed=urlsplit("https://"+value.strip().lower())
        h=parsed.hostname or ""
        if (not h or parsed.port is not None or parsed.username
            or len(h)>240 or "." not in h or ".." in h
            or not re.fullmatch("[a-z0-9.-]+",h)
            or h.endswith((".local",".internal",".localhost",".example",".invalid"))):
            return ""
        try:ipaddress.ip_address(h);return ""
        except ValueError:pass
        return h
    except ValueError:return ""

def compile_review(raw:Mapping[str,Any],*,now:datetime)->dict[str,Any]:
    require(now.tzinfo is not None,"TIME_MUST_BE_AWARE")
    require(raw.get("schema")==REVIEW_SCHEMA
        and raw.get("source_release")=="2026-10-21.0"
        and raw.get("source_data_license_permissive") is True
        and raw.get("overture_feature_sources_preserved") is True
        and raw.get("source_rows")==27
        and raw.get("buyer_approvals")==0
        and raw.get("crm_writes") is False
        and raw.get("outbound_sent") is False
        and raw.get("full_canonical_CRM_dedup") is False
        and raw.get("automatic_Scout_ingestion") is False,
        "UNVERIFIED_OR_UNSAFE_ORIGINAL_SOURCE_REPORT")
    observed=datetime.fromisoformat(str(raw.get("at_utc") or ""))
    require(observed.tzinfo is not None and
            timedelta(0)<=now-observed<=MAX_AGE,
            "ORIGINAL_SOURCE_TOO_OLD_OR_FUTURE")
    rows=raw.get("rows")
    require(isinstance(rows,list) and len(rows)<=50,"SOURCE_ROW_BUDGET")
    intake=[]
    used=set()
    for row in rows:
        if not isinstance(row,dict):raise Held("MALFORMED_SOURCE_ROW")
        if row.get("final_state")!="FIRST_PARTY_NAMED_BUSINESS_RESEARCH_ONLY":
            continue
        host=domain(str(row.get("domain") or ""))
        name=str(row.get("business_name") or "").strip()
        sources=row.get("source_datasets")
        require(bool(host) and host not in used and 5<=len(name)<=110
                and row.get("first_party_operating_name_corroborated") is True
                and row.get("buyer_intent_verified") is False
                and row.get("contact_permission_verified") is False
                and row.get("original_canonical_prospect_not_full_dedup") is True
                and isinstance(sources,list) and len(sources)>0 and
                all(isinstance(s,dict) and isinstance(s.get("dataset"),str)
                    for s in sources[:10]),
                "RESEARCH_COMPANY_SOURCE_PROOF_INVALID")
        used.add(host)
        intake.append({
          "domain":host,
          "website":"https://"+host+"/",
          "registry_business_name":name,
          "registry_location":"Dallas, TX, USA",
          "target_markets":["USA"],
          "target_buyer_pools":["local_and_smb_buyers"],
          "target_product_codes":["managed_service"],
          "source_refs":["public:overture_places:2026-10-21.0:"+host],
          "source_queries":[],
          "target_corridor_keys":[],
          "source_origin":"Overture Maps Places 2026-10-21.0 + observed first-party company website",
          "truth_class":"OBSERVED_FIRST_PARTY_COMPANY_RESEARCH_ONLY",
          "company_identity_verified":False,
          "canonical_crm_duplicate_status":"UNKNOWN_NOT_QUERIED",
          "contact_permission_verified":False,
          "outreach_authorized":False,
          "verified_product_purchasing_agreement":False,
          "verified_buyer_capacity":False,
          "commercial_terms_verified":False,
          "buyer_price_verified":False,
          "execution_authority":"none"
        })
    require(len(intake)==4,"FOUR_REVIEWED_RESEARCH_BUSINESSES_EXPECTED")
    return {
      "schema_version":INTAKE_SCHEMA,
      "mode":"OBSERVE",
      "reviewed_at_utc":observed.astimezone(timezone.utc).isoformat(),
      "source_release":"2026-10-21.0",
      "source_report_sha256":SOURCE_SHA,
      "source_trust":"ORIGINAL_OWNER_EXPLICIT_RESEARCH_RECEIPT",
      "canonical_crm_dedup_proven":False,
      "outreach_authorized":False,
      "buyer_approvals":0,"paid_api_calls":False,
      "database_writes":False,
      "execution_authority":"none",
      "seeds":intake,
    }

def read_live(root:Path,*,now:datetime|None=None)->tuple[list[dict],dict[str,Any]]:
    now=now or datetime.now(timezone.utc)
    path=root/INTAKE_RELATIVE
    try:
        require(path.is_file() and not path.is_symlink()
                and path.stat().st_size<20000,"SOURCE_RECEIPT_NOT_PRESENT")
        require(sha(path)==INTAKE_SHA,"SOURCE_RECEIPT_DIGEST_CHANGED")
        data=json.loads(path.read_text())
        require(data.get("schema_version")==INTAKE_SCHEMA
                and data.get("source_report_sha256")==SOURCE_SHA
                and data.get("canonical_crm_dedup_proven") is False
                and data.get("outreach_authorized") is False
                and data.get("buyer_approvals")==0
                and data.get("execution_authority")=="none"
                and data.get("mode")=="OBSERVE",
                "SOURCE_INTAKE_CONTRACT_UNVERIFIED")
        observed=datetime.fromisoformat(str(data.get("reviewed_at_utc") or ""))
        require(observed.tzinfo is not None
                and timedelta(0)<=now-observed<=MAX_AGE,
                "SOURCE_INTAKE_AGED_OUT")
        rows=data.get("seeds")
        require(isinstance(rows,list) and len(rows)==4,"SOURCE_INTAKE_ROW_COUNT")
        used=set()
        for row in rows:
            require(isinstance(row,dict),"INTAKE_MALFORMED_ROW")
            h=domain(row.get("domain"))
            require(h and h not in used
                    and row.get("website")=="https://"+h+"/"
                    and row.get("source_refs")==["public:overture_places:2026-10-21.0:"+h]
                    and row.get("target_buyer_pools")==["local_and_smb_buyers"]
                    and row.get("target_product_codes")==["managed_service"]
                    and row.get("canonical_crm_duplicate_status")=="UNKNOWN_NOT_QUERIED"
                    and row.get("outreach_authorized") is False
                    and row.get("execution_authority")=="none",
                    "SOURCE_INTAKE_IDENTITY_OR_RIGHTS_CHANGED")
            used.add(h)
        # Reuse only the separately authorised original Search Fabric
        # read-only public.prospects website-domain match receipt. Never read
        # tenant tables or infer a 0-match is a cleared entity or contact.
        match_path=root/PROSPECT_DUPLICATE_RELATIVE
        require(match_path.is_file() and not match_path.is_symlink()
                and match_path.stat().st_size<12000,
                "ORIGINAL_DATABASE_DOMAIN_RECEIPT_NOT_PRESENT")
        require(sha(match_path)==PROSPECT_DUPLICATE_SHA,
                "ORIGINAL_DATABASE_DOMAIN_RECEIPT_CHANGED")
        checked=json.loads(match_path.read_text())
        counts=checked.get("exact_normalised_website_domain_match_counts")
        require(checked.get("schema_version")==PROSPECT_DUPLICATE_SCHEMA
                and checked.get("research_source_sha256")==INTAKE_SHA
                and checked.get("original_canonical_prospects_total")==35278
                and checked.get("all_tenant_crm_dedupe_verified") is False
                and checked.get("contact_consent_verified") is False
                and checked.get("outbound_authorized") is False
                and checked.get("database_writes") is False
                and isinstance(counts,dict)
                and set(counts)==used
                and all(type(v) is int and 0<=v<=35278 for v in counts.values())
                and sum(v>0 for v in counts.values())==2,
                "ORIGINAL_DATABASE_DUPLICATE_COUNT_CONTRACT_CHANGED")
        unique_research=[r for r in rows if counts[r["domain"]]==0]
        require(len(unique_research)==2,"ORIGINAL_DOMAIN_SUPPRESSION_COUNT_UNEXPECTED")
        # Separately signed UK partner research is an optional observation.
        # Never weaken the original pinned Dallas admission or its proof.
        # The partner module only emits research; all identity, CRM, buying
        # and outbound gates remain with the original Buyer Scout.
        from scripts.overture_uk_partner_research_20261111 import read_partner
        uk_research,uk_state=read_partner(now=now)
        combined=[*unique_research,*uk_research]
        return combined,{
          "status":"ORIGINAL_SCOUT_OVERTURE_RESEARCH_OBSERVED",
          "source_count":len(combined),
          "uk_partner_research_source":uk_state,
          "source_rows_before_duplicate_suppression":len(rows),
          "original_public_prospect_domain_matches_suppressed":len(rows)-len(unique_research),
          "original_public_prospect_receipt_sha256":PROSPECT_DUPLICATE_SHA,
          "source_report_sha256":SOURCE_SHA,
          "canonical_crm_dedup":"PARTIAL_PUBLIC_PROSPECT_WEBSITE_ONLY",
          "all_tenant_crm_dedup_verified":False,
          "outreach_authorized":False,"buyer_approvals":0,
          "source_generated_live_requests":0
        }
    except (Held,OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        return [],{
          "status":"ORIGINAL_SCOUT_OVERTURE_RESEARCH_HELD",
          "reason":str(exc)[:100],
          "source_count":0,"canonical_crm_dedup":"UNKNOWN",
          "outreach_authorized":False,"buyer_approvals":0,
          "source_generated_live_requests":0
        }
