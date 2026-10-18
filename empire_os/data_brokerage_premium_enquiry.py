"""Two premium Data Brokerage *discovery* enquiries via existing EmpireDB CRM RPC.

Feature-only: no caller mounts this router in the production ASGI app.
All prices are unapproved internal hypotheses and NEVER accepted/published.
The actual request is buyer-initiated; processing requires authenticated
first-party gateway controls, exact response consent, bounded fields, and a
caller-supplied rate limiter BEFORE canonical CRM ingest may be invoked.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import re
from collections.abc import Callable,Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, StrictBool

from empire_os.sb import request_json
from empire_os.first_party_sales_interest import (
    CommercialInterestError,_text,_email,_domain,KEY_RE
)
from empire_os.data_brokerage_sales_activation import SAFE_OFFERS

SCHEMA="empire.data_brokerage.premium_discovery_interest.v1"
ORIGIN="https://empire-ai.co.uk"
RPC="/rest/v1/rpc/ingest_prospect_atomic"
MAX_BODY_BYTES=12_000

# These are deliberately DISTINCT from the draft price-bearing product codes.
# No recurring subscription, publicly approved price, or capacity promise.
DISCOVERY={
    "brokerage_agency_discovery":{
        "draft_offer_code":"agency_white_label_search",
        "title":"Agency Intelligence — scope discussion",
        "buyer_problem":"Evidence-linked local market research for a B2B agency",
    },
    "brokerage_enterprise_discovery":{
        "draft_offer_code":"portfolio_geography_intelligence",
        "title":"Enterprise Territory Intelligence — scope discussion",
        "buyer_problem":"Evidence-linked market selection for a multi-territory operator",
    },
}
assert {x["draft_offer_code"] for x in DISCOVERY.values()}.issubset(set(SAFE_OFFERS))

class PremiumDiscoveryRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_code:str=Field(min_length=1,max_length=80)
    business_name:str=Field(min_length=1,max_length=200)
    email:str=Field(min_length=3,max_length=320)
    domain:str=Field(min_length=3,max_length=253)
    industry:str=Field(min_length=1,max_length=120)
    geography:str=Field(min_length=1,max_length=160)
    desired_outcome:str=Field(min_length=12,max_length=1200)
    contact_consent:StrictBool
    idempotency_key:str=Field(min_length=8,max_length=128)
    website:str=Field(default="",max_length=300)

def discovery_catalog()->dict[str,Any]:
    return {
        "schema_version":SCHEMA,
        "status":"UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED",
        "offers":[{
            "product_code":code,
            "draft_source_offer_code":row["draft_offer_code"],
            "title":row["title"],
            "buyer_problem":row["buyer_problem"],
            "price_approved":False,
            "approved_price_cents":None,
            "contract_binding":False,
            "capacity_verified":False,
            "checkout_enabled":False,
            "enquiry_enabled_in_production":False,
        } for code,row in DISCOVERY.items()],
        "marketplace_listing_live":False,
        "outbound_enabled":False,
        "customer_delivery_enabled":False,
        "payment_enabled":False,
    }

def record_premium_discovery(
    raw:Mapping[str,Any], *,
    request:Callable[...,Any]=request_json,
    now:datetime|None=None,
)->dict[str,Any]:
    """Call existing canonical ingest once only after consent & input validation.

    No test/preview mode can be passed into the actual CRM. For test runs,
    callers inject an in-memory fake RPC to prove the exact payload.
    """
    if not isinstance(raw,Mapping):
        raise CommercialInterestError("invalid_premium_discovery_request")
    if set(raw)-set(PremiumDiscoveryRequest.model_fields):
        raise CommercialInterestError("unsupported_premium_discovery_fields")
    # Strict bool avoids accepting an integer, missing or implicit marketing opt-in.
    if type(raw.get("contact_consent")) is not bool or raw.get("contact_consent") is not True:
        raise CommercialInterestError("specific_response_consent_required")
    if raw.get("website","") != "":
        raise CommercialInterestError("invalid_submission")
    key=_text(raw.get("product_code"),"product_code",limit=80)
    offer=DISCOVERY.get(key)
    if offer is None:
        raise CommercialInterestError("unrecognized_premium_discovery_offer")
    business=_text(raw.get("business_name"),"business_name",limit=200)
    email=_email(raw.get("email"))
    domain=_domain(raw.get("domain"))
    industry=_text(raw.get("industry"),"industry",limit=120)
    metro=_text(raw.get("geography"),"geography",limit=160)
    brief=_text(raw.get("desired_outcome"),"desired_outcome",limit=1200)
    if len(brief)<12:
        raise CommercialInterestError("insufficient_buyer_stated_problem")
    idempotency=_text(raw.get("idempotency_key"),"idempotency_key",limit=128)
    if KEY_RE.fullmatch(idempotency) is None:
        raise CommercialInterestError("invalid_idempotency_key")
    observed=now or datetime.now(timezone.utc)
    if not isinstance(observed,datetime) or observed.tzinfo is None or observed.utcoffset() is None:
        raise CommercialInterestError("untrusted_consent_clock")
    observed_utc=observed.astimezone(timezone.utc).isoformat()
    # Only first-party request for response. No consent to newsletters.
    canonical=hashlib.sha256(f"{key}|{domain}|{idempotency}".encode("utf-8")).hexdigest()
    masked_email=hashlib.sha256(email.encode("utf-8")).hexdigest()[:24]
    evidence={
        "schema_version":SCHEMA,
        "source":"first_party_data_brokerage_premium_discovery",
        "product_code":key,
        "draft_source_offer_code":offer["draft_offer_code"],
        "buyer_stated":True,
        "buyer_statement":brief,
        "contact_email":email,
        "company_domain":domain,
        "industry":industry,
        "geography":metro,
        "contact_consent_evidence":{
            "kind":"buyer_initiated_specific_response_consent",
            "observed_at":observed_utc,
            "consent_to_contact":True,
            "newsletter_or_ongoing_marketing_consent":False,
            "source_url":"https://empire-ai.co.uk/commercial",
        },
        "internal_monthly_price_is_hypothesis":True,
        "approved_price_cents":None,
        "approved_contract_or_subscription":False,
        "commercial_capacity_verified":False,
        "source_rights_verified":False,
        "buyer_identity_qualified":False,
        "automatic_followup_authorized":False,
        "outreach_authority":"none",
        "binding_terms_ready":False,
        "checkout_authorized":False,
        "payment_action":False,
        "actual_revenue":False,
        "execution_authority":"none",
    }
    # Exact same atomic RPC used by the existing commercial interest path.
    result=request("POST",RPC,payload={
        "p_prospect":{
            "business_name":business,
            "niche":"commercial_sales:data_brokerage_premium_discovery",
            "metro":metro,
            "buy_signal_score":0,
            "contact_source":"first_party_commercial_sales_enquiry",
            "contacted_status":"not_contacted",
        },
        "p_evidence":evidence,
        "p_ingest_key":"commercial-sales:"+canonical,
        "p_identity_keys":["domain:"+domain,"email:"+masked_email],
    })
    if (not isinstance(result,Mapping)
        or result.get("decision") not in {"created","existing_ingest","existing_identity"}
        or not isinstance(result.get("prospect"),Mapping)
        or not str(result["prospect"].get("id") or "").strip()):
        raise CommercialInterestError("premium_enquiry_not_recorded")
    return {
        "schema_version":SCHEMA,
        "decision":"commercial_enquiry_recorded",
        "product_code":key,
        "reference":canonical[:20],
        "next_step":"FOUNDER_PRIVATE_SCOPE_REVIEW",
        "buyer_identity_qualified":False,
        "contact_permission_scope":"THIS_ENQUIRY_ONLY",
        "automatic_followup_sent":False,
        "terms_binding":False,
        "subscription_created":False,
        "payment_or_revenue_verified":False,
        "execution_authority":"none",
    }

def make_private_discovery_router(*,
       rate_limiter:Callable[[str,str],bool],
       request:Callable[...,Any]=request_json)->APIRouter:
    """Only approved gateway may mount this router with working rate limits.

    The *factory* does not register public routes by itself. It enforces
    same-origin and bounded input on every POST; no production invocation
    is included in the feature release.
    """
    if not callable(rate_limiter):
        raise ValueError("GATEWAY_RATE_LIMITER_REQUIRED")
    router=APIRouter()

    @router.get("/v1/brokerage/premium-discovery")
    async def get_discovery()->dict[str,Any]:
        return discovery_catalog()

    @router.post("/v1/brokerage/premium-discovery")
    async def post_discovery(req:Request)->dict[str,Any]:
        if (req.headers.get("origin")!=ORIGIN
            or req.headers.get("sec-fetch-site","same-origin") not in {"same-origin","none"}):
            raise HTTPException(status_code=403,detail="same_origin_required")
        if req.headers.get("content-type","").split(";",1)[0].strip().lower()!="application/json":
            raise HTTPException(status_code=415,detail="json_required")
        peer=req.client.host if req.client else "unknown"
        if rate_limiter(peer,"enquiry") is not True:
            raise HTTPException(status_code=429,detail="rate_limited")
        body=await req.body()
        if len(body)>MAX_BODY_BYTES:
            raise HTTPException(status_code=413,detail="request_too_large")
        try:
            payload=PremiumDiscoveryRequest.model_validate_json(body)
            return record_premium_discovery(payload.model_dump(),request=request)
        except CommercialInterestError as exc:
            # Uniform safe business-rule codes, never raw DB exception text.
            raise HTTPException(status_code=422,detail=str(exc)) from None
        except Exception as exc:
            if type(exc).__module__.startswith("pydantic"):
                raise HTTPException(status_code=422,detail="invalid_premium_discovery_request") from None
            raise HTTPException(status_code=503,detail="premium_discovery_temporarily_unavailable") from None
    return router
