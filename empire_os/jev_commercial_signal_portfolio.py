"""High-level Jev-compatible review portfolio over Empire's *existing* Intent Brain.

Input: existing pre-identity signal inbox, read-only. Intent Brain + deterministic
JEV adjudication set immutable commercial authority. Optional local Laya can
suggest review allocation, never source/identity promotion, outreach, CRM or money.
No raw source texts, page URLs, names, contact details or messages reach the model
or leave this module in its result.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import isfinite
from time import perf_counter
import json
import re
from typing import Any, Mapping

from empire_os.intent_brain_actor import run_intent_brain_actor
from empire_os.signal_intent_actor_router import observation_from_signal
from empire_os.typed_decision_provider import (
    TypedDecisionRequest, review_typed_decision_result,
)

SCHEMA="empire.jev.commercial_signal_portfolio.v1"
SOURCE_TYPES=frozenset(("reddit_intent","linkedin_intent"))
VALID_STATUSES=frozenset(("unresolved","needs_review"))
ALLOWED_NICHES=frozenset(("roofing","solar","hvac","dental","legal","property"))
MODEL_LANES=("REVIEW_IDENTITY","REVIEW_EVIDENCE","REVIEW_BUYER_CAPACITY","MONITOR","DISCARD")
DETERMINISTIC_LANES={
    "REJECT":"DISCARD",
    "WATCH":"MONITOR",
    "RESOLVE_IDENTITY":"REVIEW_IDENTITY",
    "NEEDS_REVIEW":"REVIEW_EVIDENCE",
    "BUYER_SCOUT_SEED":"REVIEW_BUYER_CAPACITY",
}
REVIEW_ORDER={
    "REVIEW_BUYER_CAPACITY":0,
    "REVIEW_IDENTITY":1,
    "REVIEW_EVIDENCE":2,
    "MONITOR":3,
    "DISCARD":4,
}
HEX64=re.compile(r"^[a-f0-9]{64}$")
MAX_REVIEW=60
MAX_MODEL=3


def _digest(value:str)->str:
    return sha256(value.encode("utf8")).hexdigest()


def _safe_niche(value:Any)->str:
    return value if type(value) is str and value in ALLOWED_NICHES else "other"


def review_existing_intent_signals(
    inbox: Mapping[str,Any], *, provider:Any=None,
    max_signals:int=40, model_call_budget:int=0,
    minimum_model_confidence:float=.8,
)->dict[str,Any]:
    """Produce non-executable decision portfolio; every row validates pre-model."""
    if (type(max_signals) is not int or not 1<=max_signals<=MAX_REVIEW
        or type(model_call_budget) is not int or not 0<=model_call_budget<=MAX_MODEL
        or type(minimum_model_confidence) not in (int,float)
        or not isfinite(minimum_model_confidence)
        or not .5<=minimum_model_confidence<=1):
        raise ValueError("bounded portfolio parameters required")
    if (model_call_budget>0 and
        (provider is None or not callable(getattr(provider,"evaluate",None)))):
        raise ValueError("explicit local typed provider required")
    if not isinstance(inbox,Mapping) or len(inbox)>25000:
        raise ValueError("unbounded or absent existing signal inbox")
    started=perf_counter()
    eligible=[]
    source_counts=Counter()
    for source_id,record in inbox.items():
        if not isinstance(record,Mapping):
            continue
        if record.get("source") not in SOURCE_TYPES:
            continue
        source_counts[record["source"]]+=1
        if record.get("status") not in VALID_STATUSES:
            continue
        if (not isinstance(source_id,str) or not 1<=len(source_id)<=256
            or not isinstance(record.get("raw"),Mapping)):
            raise ValueError("unsafe unresolved intent source record")
        if (record.get("execution_authority")!="none"
            or record.get("entity_id") is not None
            or record.get("prospect_id") is not None):
            raise ValueError("input is not canonical pre-identity signal")
        eligible.append((source_id,record))
    # Deterministic, reproducible selection order. Don't use arbitrary 'score'
    # or a timestamp string to claim that observations are verified or new.
    eligible.sort(key=lambda x:(str(x[1].get("last_seen_at") or ""),
                                _digest(x[0])),reverse=True)
    selected=eligible[:max_signals]
    work=[]
    duplicates=0
    seen_origins=set()
    for signal_id,record in selected:
        observation=observation_from_signal(signal_id,record)
        if observation is None:
            raise ValueError("unexpected invalid current intent observation")
        # NEVER inherit a first-party verification claim from untrusted user
        # text, external social media or the raw pre-identity inbox record.
        observation["first_party_verified"]=False
        observation.pop("trusted_buyer_receipt",None)
        event_source=str(record.get("source"))
        link=observation.get("url")
        # Hash link for dedupe only; no URLs or raw identity in output/model.
        link_key=(event_source+":"+str(link).strip().lower()) if isinstance(link,str) and link.strip() else (event_source+":"+signal_id)
        key=_digest(link_key)
        if key in seen_origins:
            duplicates+=1
            continue
        seen_origins.add(key)
        envelope=run_intent_brain_actor(observation)
        governance=envelope["governance"]
        if (envelope.get("schema_version")!="empire.revenue_actor.v1"
            or envelope.get("actor",{}).get("actor_key")!="intent_brain"
            or governance.get("execution_authority")!="none"
            or any(governance.get(k) is not False for k in (
                "outreach_authorized","database_write_performed",
                "canonical_promotion_performed","payment_mutation",
                "content_posted","actual_revenue"))):
            raise ValueError("Intent Brain actor authority violation")
        commercial=envelope["output"]["commercial_state"]
        jev=envelope["output"]["jev"]
        if (jev.get("execution_authority")!="none"
            or jev.get("outreach_authorized") is not False
            or jev.get("database_write_performed") is not False
            or jev.get("first_party_identity_verified") is not False):
            raise ValueError("noncanonical JEV adjudication authority")
        decision=envelope["decision"]
        if decision not in DETERMINISTIC_LANES:
            raise ValueError("unknown canonical intent decision")
        lane=DETERMINISTIC_LANES[decision]
        # An actor may never create a high-authority buyer seed from this
        # pre-identity path; such status requires a separately verified source.
        if decision=="BUYER_SCOUT_SEED":
            raise ValueError("pre-identity observation cannot produce seed")
        work.append({
            "signal_event_sha256":_digest(signal_id),
            "source_reference_sha256":key,
            "actor_input_sha256":envelope["run"]["input_fingerprint"],
            "channel":event_source,
            "niche":_safe_niche(commercial.get("niche")),
            "actor_class":(commercial.get("actor_state")
                           if commercial.get("actor_state") in
                           ("owner_operator","decision_maker","job_seeker","vendor","unknown")
                           else "unknown"),
            "deterministic_intent_decision":decision,
            "deterministic_review_lane":lane,
            "contradictions_present":jev.get("contradiction_count",0)>0,
            "identity_verified":False,
            "verified_buyer_capacity":False,
            "commercial_demand_verified":False,
            "proposed_model_lane":None,
            "shadow_status":"NOT_CALLED",
            "requires_human_review":lane!="DISCARD",
        })
    work.sort(key=lambda row:(REVIEW_ORDER[row["deterministic_review_lane"]],
                              row["source_reference_sha256"]))
    # All input and authority validation is complete before model calls.
    called=0
    for row in work:
        if called>=model_call_budget:
            break
        if row["deterministic_review_lane"] in ("DISCARD","MONITOR"):
            continue
        called+=1
        request=TypedDecisionRequest(
            task_key="commercial_signal_portfolio",
            decision_schema_ref=SCHEMA,
            state_ref=row["signal_event_sha256"],
            state={
                "niche":row["niche"],"channel":row["channel"],
                "actor_class":row["actor_class"],
                "deterministic_lane":row["deterministic_review_lane"],
                "contradictions":row["contradictions_present"],
                "identity_verified":False,"buyer_capacity_verified":False,
                "source_review_only":True,
            },
            allowed_labels=MODEL_LANES,risk_class="high",
            instructions=(
                "Choose only an internal review queue. Do not infer that an "
                "unverified person is a buyer. Never authorise outreach, "
                "identity promotion or revenue."),
        )
        try:
            response=provider.evaluate(request)
            checked=review_typed_decision_result(
                request=request,result=response,
                confidence_threshold=minimum_model_confidence)
            if (response.shadow_only is not True
                or response.execution_authority!="none"
                or response.provider_key not in ("laya_http","laya")
                or not isfinite(response.latency_ms)):
                raise ValueError("nonlocal or nonshadow typed provider")
            row["proposed_model_lane"]=response.label
            row["shadow_status"]=(
                "SHADOW_ESCALATE" if checked["requires_escalation"]
                or response.label!=row["deterministic_review_lane"]
                else "SHADOW_AGREES_REVIEW_ONLY")
            row["local_model_latency_ms"]=response.latency_ms
        except Exception:
            row["shadow_status"]="SHADOW_UNAVAILABLE_HELD"
    elapsed=(perf_counter()-started)*1000
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"EXECUTIVE_INTENT_PORTFOLIO_REVIEW_ONLY",
        "source_types_considered":dict(sorted(source_counts.items())),
        "eligible_unresolved_signals":len(eligible),
        "signals_selected_for_review":len(selected),
        "duplicate_source_refs_collapsed":duplicates,
        "review_item_count":len(work),
        "lane_counts":dict(sorted(Counter(r["deterministic_review_lane"]
                                          for r in work).items())),
        "local_model_attempts":called,
        "elapsed_ms_including_shadow":round(elapsed,3),
        "items":work,
        "canonical_prospects_created":0,
        "identity_promotions":0,
        "buyer_capacity_verified":False,
        "outreach_sent":0,"lead_sales_verified":0,
        "actual_revenue":False,
        "database_writes":False,"execution_authority":"none",
    }
