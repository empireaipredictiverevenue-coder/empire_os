"""Source-backed UK heat pump expansion intake for the EXISTING Buyer Network.

Does not create an agent, lead or CRM buyer record. Public partner pages are
research receipts, not proof of paying interest or accepted lead terms.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
from typing import Any
from urllib.parse import urlparse

from scripts.reconcile_buyer_email_relationships import atomic_private_write

SCHEMA = "empire.buyer_network.heat_pump_public_expansion.v1"
SEED = Path("docs/commercial/HEAT_PUMP_MARKET_EXPANSION_SEEDS_20261026.tsv")
REL = Path("runtime/buyer_network_intelligence")
DEST = REL/"heat_pump_public_expansion_review_latest.json"
DOM = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
ROLES = {
    "b2b_referral_programme", "b2b_affiliate_and_installer",
    "consumer_referral_restricted", "installer_customer_acquisition",
    "installer_partnership_network", "referral_and_distribution_network",
    "installer_partner_marketplace", "lead_supplier_intermediary",
}
COLUMNS = ("company","website_domain","commercial_role","published_signal","proof_url","limitation")
MAX_BYTES = 90_000

def safe_read(path: Path, maxbytes: int) -> bytes:
    if (path.is_symlink() or not path.is_file() or not
            20 < path.stat().st_size <= maxbytes):
        raise ValueError("ORIGINAL_SOURCE_MISSING_OR_UNSAFE:"+path.name)
    return path.read_bytes()

def normalize(value: str) -> str:
    return str(value).strip().lower().removeprefix("www.")

def index_existing(registry: dict, queue: dict) -> dict[str, dict]:
    if (not isinstance(registry, dict)
            or registry.get("schema_version") != "empire.commercial_relationship_registry.v1"
            or not isinstance(registry.get("relationships"),list)
            or not isinstance(queue,dict)
            or not isinstance(queue.get("candidates"),list)):
        raise ValueError("ORIGINAL_REGISTRY_OR_QUEUE_NOT_RECOGNIZED")
    results={}
    for row in registry["relationships"]:
        if not isinstance(row,dict):
            continue
        for value in row.get("identity_domains",[]):
            key=normalize(value)
            if DOM.fullmatch(key):
                results.setdefault(key,{})["registry"] = {
                    "stage":row.get("stage"),
                    "last_outbound_at":row.get("last_outbound_at"),
                    "do_not_pursue":row.get("do_not_pursue"),
                    "gmail_thread_count":len(row.get("gmail_thread_ids",[])),
                }
    for row in queue["candidates"]:
        if not isinstance(row,dict):
            continue
        key=normalize(row.get("domain",""))
        if DOM.fullmatch(key):
            history=row.get("contact_history") or {}
            results.setdefault(key,{})["scout"] = {
                "contact_state":history.get("state"),
                "contact_next_action":history.get("next_action"),
                "confirmed_hard_bounce":history.get("confirmed_hard_bounce",False),
                "last_outbound_at":history.get("last_outbound_at"),
                "status":row.get("status"),
            }
    return results

def materialize(seed_bytes: bytes, registry: dict, queue: dict, *, now: datetime) -> dict:
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("TRUSTED_CLOCK_REQUIRED")
    reader=csv.DictReader(io.StringIO(seed_bytes.decode("utf-8")),delimiter="\t")
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("UNRECOGNIZED_PUBLIC_RESEARCH_SEED_SCHEMA")
    old=index_existing(registry,queue)
    rows=[]
    seen=set()
    for source in reader:
        if len(rows)>=100:
            raise ValueError("UNBOUNDED_PUBLIC_RESEARCH_BATCH")
        company=source["company"].strip()
        domain=normalize(source["website_domain"])
        url=source["proof_url"].strip()
        parsed=urlparse(url)
        host=normalize(parsed.hostname or "")
        role=source["commercial_role"].strip()
        if (not 1<=len(company)<=90
                or domain in seen or not DOM.fullmatch(domain)
                or role not in ROLES
                or parsed.scheme!="https" or not DOM.fullmatch(host)
                or parsed.username or parsed.password
                or not 10<=len(url)<=400
                or not 10<=len(source["published_signal"])<=250
                or not 10<=len(source["limitation"])<=250):
            raise ValueError("INVALID_OR_DUPLICATE_PUBLIC_RESEARCH_TARGET:"+domain)
        seen.add(domain)
        current=old.get(domain,{})
        scout=current.get("scout") or {}
        known=current.get("registry") or {}
        sent=scout.get("contact_state") in (
            "ALREADY_CONTACTED","WORKSPACE_SENT_ALREADY_CONTACTED",
            "EXISTING_CONVERSATION","EXISTING_CONVERSATION_PARTIAL_BOUNCE",
            "DELIVERY_HOLD","FOUNDER_FORM_SUBMITTED")
        sent=sent or bool(scout.get("last_outbound_at")) or bool(known.get("last_outbound_at"))
        suppression=bool(known.get("do_not_pursue") or scout.get("confirmed_hard_bounce"))
        special=(domain=="newpoweruk.co.uk")
        if suppression:
            contact="SUPPRESSED_OR_BOUNCED_DO_NOT_SEND"
        elif sent:
            contact="PRIOR_OUTBOUND_REVIEW_THREAD_NO_DUPLICATE"
        elif special:
            contact="POSSIBLE_NEWPOWER_ADVANCED_ALIAS_VERIFY_NO_DUPLICATE"
        elif known or scout:
            contact="EXISTING_RESEARCH_RECORD_RECONCILE_NO_AUTO_OUTREACH"
        else:
            contact="NO_EXACT_MATCH_RESEARCH_ONLY_NOT_PROOF_UNCONTACTED"
        direct=role in ("b2b_referral_programme","b2b_affiliate_and_installer")
        if direct:
            priority="A_B2B_TERMS_RESEARCH"
        elif role in ("consumer_referral_restricted","installer_customer_acquisition"):
            priority="B_INSTALLER_QUALIFICATION"
        elif role=="lead_supplier_intermediary":
            priority="C_SUPPLY_EXCHANGE_RESEARCH"
        else:
            priority="B_NETWORK_PARTNERSHIP_RESEARCH"
        rows.append({
            "company":company,"domain":domain,
            "public_role":role,"commercial_research_lane":priority,
            "public_evidence_claim":source["published_signal"].strip(),
            "source_url":url,
            "source_class":("FIRST_PARTY_OR_SAME_BRAND_PUBLISHED" if
                            host==domain or host.endswith("."+domain)
                            else "SECONDARY_PUBLIC_EVIDENCE_CONFIRM_WITH_FIRST_PARTY"),
            "public_terms_limitation":source["limitation"].strip(),
            "original_registry_or_scout_present":bool(current),
            "original_contact_state":contact,
            "preexisting_registry_stage":known.get("stage"),
            "preexisting_scout_contact_state":scout.get("contact_state"),
            "outreach_authorized":False,"buyer_acceptance_verified":False,
            "lead_purchase_terms_verified":False,"settlement_verified":False,
            "safe_next_action":"ORIGINAL_BUYER_SCOUT_RESEARCH_AND_FOUNDER_REVIEW_ONLY",
        })
    if len(rows)<25:
        raise ValueError("PUBLIC_RESEARCH_EXPANSION_TOO_SMALL")
    priority_order={"A_B2B_TERMS_RESEARCH":0,"B_INSTALLER_QUALIFICATION":1,
                    "B_NETWORK_PARTNERSHIP_RESEARCH":2,"C_SUPPLY_EXCHANGE_RESEARCH":3}
    rows.sort(key=lambda x:(priority_order[x["commercial_research_lane"]],x["company"].lower()))
    return {
        "schema_version":SCHEMA,"status":"EXPANDED_PUBLIC_RESEARCH_REVIEW_ONLY",
        "source_sha256":hashlib.sha256(seed_bytes).hexdigest(),
        "generated_at":now.astimezone(timezone.utc).isoformat(),
        "mode":"OBSERVE","destination_owner":"original_buyer_acquisition_scout_research",
        "candidate_count":len(rows),
        "role_counts":dict(sorted(Counter(x["public_role"] for x in rows).items())),
        "lane_counts":dict(sorted(Counter(x["commercial_research_lane"] for x in rows).items())),
        "existing_registry_or_scout_exact_matches":sum(x["original_registry_or_scout_present"] for x in rows),
        "prior_contact_or_identity_collision_reviews":sum(
            x["original_contact_state"] in ("PRIOR_OUTBOUND_REVIEW_THREAD_NO_DUPLICATE",
               "POSSIBLE_NEWPOWER_ADVANCED_ALIAS_VERIFY_NO_DUPLICATE") for x in rows),
        "fresh_research_only_without_exact_match":sum(
            x["original_contact_state"]=="NO_EXACT_MATCH_RESEARCH_ONLY_NOT_PROOF_UNCONTACTED" for x in rows),
        "not_a_confirmed_paying_buyer_count":len(rows),
        "prior_four_live_heat_pump_sent_threads_preserved":4,
        "source_and_consent_rights_unverified":True,
        "crm_buyer_records_inserted":0,
        "buyer_acceptance_verified":False,"verified_capacity":0,
        "eligible_payable_agreements":0,
        "outbound_authorized":False,"funds_authorized":False,
        "database_writes":False,
        "manual_review_required_before_contact":True,
        "companies":rows,
    }

def run(root: Path,*,now:datetime|None=None,write:bool=False)->dict:
    seed=safe_read(root/SEED,MAX_BYTES)
    registry=json.loads(safe_read(root/REL/"commercial_relationship_registry_latest.json",3_000_000))
    queue=json.loads(safe_read(root/REL/"candidate_queue_latest.json",3_000_000))
    result=materialize(seed,registry,queue,now=now or datetime.now(timezone.utc))
    if write:
        target=root/DEST
        if target.exists() and (target.is_symlink() or not target.is_file()
                or stat.S_IMODE(target.stat().st_mode)!=0o600):
            raise ValueError("EXISTING_EXPANSION_REVIEW_UNSAFE")
        atomic_private_write(target,result)
    return result
