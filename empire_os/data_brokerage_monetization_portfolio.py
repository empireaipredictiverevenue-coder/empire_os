"""Empire AI — rights-constrained *candidate* revenue models for existing data products.

No offer is published, billed, licensed, sold, or approved by this catalogue.
All prices below are founder research hypotheses, not market observations.
Uses only the four existing canonical product classes and original analysis.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.data_brokerage_product_catalog import (
    PRODUCT_IDS, validate_internal_brokerage_catalog
)

SCHEMA="empire.data_brokerage.monetization_portfolio.v1"
# Internal hypotheses. No observed conversion, contract, live source terms,
# market pricing, API SLA, or customer deliverability is implied.
# Fields: code, title, buyer, source ID, currency, proposed price, unit,
# research/evidence requirement, priority.
_MODELS=(
 ("roofing_competitor_report","Competitor Search Gap","Roofing and trade businesses",PRODUCT_IDS[3],"USD",199,"one_time_report","BUYER_SCOPE_AND_CURRENT_SERP_PAGE_EVIDENCE",0),
 ("local_search_change_watch","Local Search Change Intelligence","Roofing, solar, HVAC and dental operators",PRODUCT_IDS[3],"USD",499,"month","REPEATED_GEO_SERP_MEASUREMENT",1),
 ("agency_white_label_search","Agency White-label Market Briefs","SEO agencies and web studios",PRODUCT_IDS[3],"USD",1250,"month","EVIDENCE_LINKED_ORIGINAL_REPORTS_AND_AGENCY_TERMS",0),
 ("regional_contractor_opportunity_watch","Contractor Opportunity Monitor","Commercial contractors and distributors",PRODUCT_IDS[1],"USD",1500,"month","REAL_PERMIT_EVENT_DATES_AND_REUSE_RIGHTS",1),
 ("permit_revision_verification","Permit Revision Verification","Contractors, lenders and construction investors",PRODUCT_IDS[1],"USD",999,"month","TRUE_ISSUANCE_REVISION_DIFFERENTIAL_AND_RIGHTS",1),
 ("brownfield_site_watch","Brownfield Site Intelligence","Developers, land advisers and project investors",PRODUCT_IDS[0],"GBP",1500,"month","OGL_FIELD_RIGHTS_PRIVACY_AND_NEW_SOURCE_OBSERVATION",1),
 ("property_due_diligence_dossier","Property and Location Diligence","Commercial property investors and developers",PRODUCT_IDS[0],"GBP",3500,"project","SOURCE_RIGHTS_PROPERTY_IDENTITY_AND_ORIGINAL_ANALYSIS",1),
 ("portfolio_geography_intelligence","Multi-site Territory Intelligence","PE-backed service groups and franchise operators",PRODUCT_IDS[3],"USD",4000,"month","MULTI_MARKET_FRESHNESS_AND_BUYER_OUTCOMES",1),
 ("insurance_repair_network_brief","Repair Network Territory Intelligence","Insurers, TPAs and managed repair operators",PRODUCT_IDS[3],"USD",2500,"month","BUSINESS_ONLY_SIGNAL_VALIDATION_NO_CLAIMANT_PII",1),
 ("procurement_and_capacity_brief","Supply and Capacity Signals","Suppliers, wholesalers and commercial contractors",PRODUCT_IDS[1],"USD",2000,"month","NEW_PROJECT_PROOF_REAL_DEMAND_AND_RIGHTS",2),
 ("private_market_custom_analysis","Bespoke Investment Intelligence","Family offices, investors and infrastructure funds",PRODUCT_IDS[3],"USD",7500,"project","CUSTOM_SCOPE_SOURCES_AND_METHOD_VERIFICATION",1),
 ("licensed_intelligence_api","Predictive Opportunity Intelligence API","SaaS products, data teams and CRM vendors",PRODUCT_IDS[3],"USD",3000,"month","SIGNED_API_TERMS_PROVEN_UPDATES_AND_ACCESS_METERING",2),
 ("exclusive_territory_license","Exclusive Territory Intelligence Licence","Enterprise buyer or national channel partner",PRODUCT_IDS[3],"USD",30000,"year","EXCLUSIVITY_BOUNDARY_DELIVERABLE_RIGHTS_AND_COUNSELLED_TERMS",2),
 ("agency_broker_reseller_license","Agency and Channel Partner Licence","Marketing and implementation partner networks",PRODUCT_IDS[3],"USD",2500,"month","DERIVATIVE_LICENSE_RIGHTS_TERRITORY_AND_ATTRIBUTION",1),
)
_CHANNELS=(
 ("direct_enterprise","Empire AI direct B2B contracts",0,"NATIVE_EXISTING_CRM_AND_CONSOLE","NO_PUBLISHING_NEW_INFRASTRUCTURE"),
 ("agency_partners","Private agency and white-label referrals",0,"EXISTING_PARTNER_AND_EMAIL_FIRST_WORKFLOW","PARTNER_SCOPE_AND_RIGHTS_SIGNOFF"),
 ("datarade","Datarade commission-only discovery",1,"EXTERNAL_MARKETPLACE_REVIEW","PROVIDER_APPROVAL_RIGHTS_TO_COMMERCIALIZE_AND_PLATFORM_COMMISSION"),
 ("aws_data_exchange","AWS Data Exchange private products or API",2,"EXTERNAL_PAID_PLATFORM","PROVIDER_QUALIFICATION_LEGAL_ELIGIBILITY_SUPPORT_AND_BILLING"),
 ("snowflake_marketplace","Snowflake usage-based or subscription listings",2,"EXTERNAL_PAID_PLATFORM","FULL_ELIGIBLE_ACCOUNT_PROVIDER_PAYOUT_AND_PAID_LISTING_REVIEW"),
 ("databricks_marketplace","Databricks private exchange and commercial requests",2,"EXTERNAL_PAID_PLATFORM","PREMIUM_UNITY_CATALOG_AND_MARKETPLACE_PROVIDER_SETUP"),
)

def build_monetization_portfolio(
    private_catalog: Mapping[str, Any],
    *, assessed_at: datetime | None = None,
) -> dict[str, Any]:
    """Fail closed on existing private source authority; derive internal *options*."""
    if not validate_internal_brokerage_catalog(private_catalog):
        raise ValueError("UNTRUSTED_EXISTING_DATA_BROKERAGE_CATALOG")
    clock=assessed_at or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_ASSESSMENT_REQUIRED")
    offers=[]
    for code,name,buyer,source,currency,price,unit,evidence,priority in _MODELS:
        original = next((p for p in private_catalog["products"]
                         if p.get("product_id")==source),None)
        if original is None:
            raise ValueError("SOURCE_PRODUCT_ID_UNVERIFIED")
        offers.append({
            "offer_code":code,"name":name,"buyer_segment":buyer,
            "existing_product_id":source,
            "price_hypothesis":{"currency":currency,"amount":price,"unit":unit,
                                "market_price_verified":False,"buyer_accepted":False},
            "priority":priority,
            "evidence_required_before_offer":evidence,
            "derived_analysis_only":True,
            "no_unlicensed_raw_source_rows":True,
            "no_personal_contact_list_resale":True,
            "source_class":original["source_origin_class"],
            "existing_product_state":original["offer_state"],
            "source_specific_delivery_rights_verified":False,
            "published":False,"customer_entitlement_created":False,
            "subscription_active":False,"signed_agreement_verified":False,
            "buyer_verified":False,"payment_verified":False,
            "fulfilment_verified":False,"revenue_verified":False,
            "offer_status":"INTERNAL_COMMERCIAL_HYPOTHESIS",
        })
    channels=[
        {
            "channel_code":code,"label":label,
            "priority":priority,"route":route,
            "entry_requirements":gates,
            "account_registered_or_approved":False,
            "listing_published":False,
            "customer_entitlements_issued":False,
            "payments_processed":False,
        }
        for code,label,priority,route,gates in _CHANNELS
    ]
    # A deterministic digest proves local structural consistency only, not
    # external rights, attribution, buyer acceptance or publisher approval.
    fingerprint=sha256(json.dumps(
        [{"offer_code":x["offer_code"],"source":x["existing_product_id"],
          "price":x["price_hypothesis"]} for x in offers],
        sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"DATA_BROKERAGE_MULTICHANNEL_PRICING_HYPOTHESES_PREPARED",
        "assessed_at_utc":clock.astimezone(timezone.utc).isoformat(),
        "existing_product_count":len(PRODUCT_IDS),
        "option_count":len(offers),"route_count":len(channels),
        "options":offers,"routes":channels,
        "hypothesis_digest_not_external_signature":fingerprint,
        "additional_source_spend_gbp":0,
        "new_service_or_database_required":False,
        "provider_account_connection_performed":False,
        "raw_third_party_data_resale_authorized":False,
        "personal_data_trading_authorized":False,
        "copyright_clearance_or_license_granted":False,
        "customer_data_delivery_enabled":False,
        "outbound_authorized":False,"outbound_sent":False,
        "live_api_enabled":False,"financial_gate_changed":False,
        "payment_processed":False,"realised_revenue_verified":False,
        "database_writes":False,"execution_authority":"NONE",
    }

def validate_portfolio(candidate:Mapping[str,Any])->bool:
    if not isinstance(candidate,Mapping):
        return False
    if (candidate.get("schema_version")!=SCHEMA
        or candidate.get("status")!="DATA_BROKERAGE_MULTICHANNEL_PRICING_HYPOTHESES_PREPARED"
        or candidate.get("mode")!="OBSERVE"
        or candidate.get("existing_product_count")!=len(PRODUCT_IDS)
        or candidate.get("option_count")!=len(_MODELS)
        or candidate.get("route_count")!=len(_CHANNELS)
        or any(candidate.get(field) is not False for field in (
            "new_service_or_database_required","provider_account_connection_performed",
            "raw_third_party_data_resale_authorized","personal_data_trading_authorized",
            "copyright_clearance_or_license_granted",
            "customer_data_delivery_enabled","outbound_authorized","outbound_sent",
            "live_api_enabled","financial_gate_changed","payment_processed",
            "realised_revenue_verified","database_writes"))
        or candidate.get("execution_authority")!="NONE"):
        return False
    options=candidate.get("options")
    routes=candidate.get("routes")
    if type(options) is not list or len(options)!=len(_MODELS):
        return False
    if type(routes) is not list or len(routes)!=len(_CHANNELS):
        return False
    if len({p.get("offer_code") for p in options if type(p) is dict})!=len(_MODELS):
        return False
    # No downstream consumer may reinterpret a hypothesis as an actual
    # source licence, product SKU, verified market price or sold contract.
    for proposal,original in zip(options,_MODELS):
        if type(proposal) is not dict:
            return False
        code,name,buyer,source,currency,price,unit,evidence,priority=original
        if (proposal.get("offer_code")!=code
            or proposal.get("name")!=name
            or proposal.get("buyer_segment")!=buyer
            or proposal.get("existing_product_id")!=source
            or proposal.get("priority")!=priority
            or proposal.get("evidence_required_before_offer")!=evidence
            or proposal.get("price_hypothesis")!={
                "currency":currency,"amount":price,"unit":unit,
                "market_price_verified":False,"buyer_accepted":False
            } or proposal.get("signed_agreement_verified") is not False
            or proposal.get("subscription_active") is not False
            or proposal.get("no_unlicensed_raw_source_rows") is not True
            or proposal.get("no_personal_contact_list_resale") is not True):
            return False
    for route,original in zip(routes,_CHANNELS):
        if type(route) is not dict:
            return False
        code,name,priority,kind,gates=original
        if (route.get("channel_code")!=code or route.get("label")!=name
            or route.get("priority")!=priority or route.get("route")!=kind
            or route.get("entry_requirements")!=gates
            or route.get("customer_entitlements_issued") is not False):
            return False
    return all(
        type(p) is dict and p.get("offer_status")=="INTERNAL_COMMERCIAL_HYPOTHESIS"
        and p.get("published") is False and p.get("customer_entitlement_created") is False
        and p.get("buyer_verified") is False and p.get("payment_verified") is False
        and p.get("revenue_verified") is False and p.get("derived_analysis_only") is True
        and p.get("source_specific_delivery_rights_verified") is False
        and p.get("existing_product_id") in PRODUCT_IDS
        and type(p.get("price_hypothesis",{}).get("amount")) is int
        and p["price_hypothesis"]["market_price_verified"] is False
        for p in options
    ) and all(
        type(c) is dict and c.get("listing_published") is False
        and c.get("account_registered_or_approved") is False
        and c.get("payments_processed") is False
        for c in routes
    )
