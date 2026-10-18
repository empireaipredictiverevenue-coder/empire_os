"""Read-side commercial handoff from existing Empire Data Brokerage to Sales/CRM.

Derives scopes from the current 14-option price hypotheses and from a proven
private first-sale source receipt. Never certifies buyer, contract, capacity,
IP rights, payment, live marketing, marketplace provider account or forecast.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.data_brokerage_monetization_portfolio import (
    SCHEMA as PORTFOLIO_SCHEMA, validate_portfolio,
)

SCHEMA = "empire.data_brokerage.sales_activation_review.v1"
SAFE_OFFERS = (
    "roofing_competitor_report",
    "agency_white_label_search",
    "portfolio_geography_intelligence",
)
# Exact reviewed portfolio hypotheses only, not prices accepted by buyers.
EXPECTED_PRICE_HYPOTHESES = {
    "roofing_competitor_report":("USD",199,"one_time_report"),
    "agency_white_label_search":("USD",1250,"month"),
    "portfolio_geography_intelligence":("USD",4000,"month"),
}
# These are *conditional, proposed* report contents for a human to negotiate;
# never a statement that Empire has measured live SERPs or can fulfil volumes.
PLAYBOOK = {
    "roofing_competitor_report": {
        "commercial_track":"ENTRY_REPORT",
        "buyer_type":"Single-location roofing business",
        "one_line_value":"Measure one trade/service in one metro with original evidence-linked competitor research",
        "proposed_delivery":"One source-cited written report, three to five reviewed pages, five prioritised recommendations",
        "pilot_capacity_promise_authorized":False,
        "minimum_evidence":[
            "EXACT_BUYER_DECISION_MAKER_AND_SCOPE_ACCEPTANCE",
            "DATED_CURRENT_LOCAL_SERP_SEARCH_AND_PAGE_SOURCES",
            "PUBLISHER_REUSE_RIGHTS_AND_ORIGINAL_REPORT_QA",
            "VERIFIED_PAYMENT_ROUTE_AND_SCOPE_TERMS",
        ],
        "sales_owner_lane":"existing_founder_sales_and_crm",
        "delivery_owner_lane":"existing_marketing_research_and_content",
    },
    "agency_white_label_search": {
        "commercial_track":"RECURRING_AGENCY_PILOT",
        "buyer_type":"B2B SEO or web agency with active trade-service client demand",
        "one_line_value":"Evidence-linked local market competitor briefs under negotiated agency usage terms",
        "proposed_delivery":"Proposed pilot: two custom market briefs per month plus monthly synthesis and one correction round, subject to verified capacity",
        "pilot_capacity_promise_authorized":False,
        "minimum_evidence":[
            "VERIFIED_AGENCY_PARTNER_PERSON_AND_SCOPE_ACCEPTANCE",
            "CLIENT_TERRITORY_AND_WHITE_LABEL_USAGE_LIMITS",
            "TWO_FRESH_SERP_SOURCE_SETS_AND_REPORT_QUALITY_REVIEW",
            "AGREED_MONTHLY_CAPACITY_PRICE_BILLING_CANCELLATION",
            "ACTUAL_DELIVERY_RIGHTS_AND_SOURCE_ATTRIBUTION",
        ],
        "sales_owner_lane":"existing_strategic_partnerships_and_crm",
        "delivery_owner_lane":"existing_marketing_research_and_content",
    },
    "portfolio_geography_intelligence": {
        "commercial_track":"ENTERPRISE_TERRITORY_PILOT",
        "buyer_type":"Multi-location roofing, solar, HVAC or dental operator",
        "one_line_value":"Compare multiple territories for verifiable commercial search coverage and expansion decisions",
        "proposed_delivery":"Proposed pilot: three defined markets, dated source matrix, evidence confidence and prioritised territory review, subject to verified capacity",
        "pilot_capacity_promise_authorized":False,
        "minimum_evidence":[
            "VERIFIED_ENTERPRISE_ECONOMIC_BUYER_AND_EXPANSION_PROBLEM",
            "THREE_EXACT_MARKETS_SEGMENTS_AND_LICENCE_SCOPE",
            "CURRENT_EVIDENCE_COVERAGE_AND_LIMITATION_REVIEW",
            "DOCUMENTED_KPI_DEFINITION_NO_FORECAST_INVENTION",
            "SIGNED_USAGE_TERMS_PAYMENT_AND_REPORT_ACCEPTANCE",
        ],
        "sales_owner_lane":"existing_founder_sales_and_strategic_partnerships",
        "delivery_owner_lane":"existing_predictive_intelligence_and_marketing_research",
    },
}

def build_sales_activation_review(portfolio: Mapping[str,Any],
                                  private_closeout: Mapping[str,Any],
                                  *, now:datetime|None=None) -> dict[str,Any]:
    if not validate_portfolio(portfolio):
        raise ValueError("UNTRUSTED_MONETIZATION_PORTFOLIO")
    if (not isinstance(private_closeout,Mapping)
        or private_closeout.get("status")!="BROKERAGE_PRIVATE_SAMPLE_VERIFIED_FIRST_SALE_HELD"
        or private_closeout.get("mode")!="OBSERVE"
        or private_closeout.get("original_report_private_and_integrity_verified") is not True
        or private_closeout.get("report_sha256")!="59b53c1e855481017484694e2ae7c3c3e4517394f39b599eeb8086269af2482a"
        or private_closeout.get("first_sale_ready") is not False
        or private_closeout.get("revenue_or_payment_verified") is not False
        or private_closeout.get("buyer_accepted_scope_verified") is not False
        or private_closeout.get("database_mutation") is not False
        or private_closeout.get("outbound_sent") is not False
        or private_closeout.get("payment_executed") is not False):
        raise ValueError("UNTRUSTED_FIRST_SALE_PROVENANCE_OR_AUTHORITY")
    moment=now or datetime.now(timezone.utc)
    if not isinstance(moment,datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("TZ_AWARE_CLOCK_REQUIRED")
    items={o["offer_code"]:o for o in portfolio["options"]}
    packages=[]
    for code in SAFE_OFFERS:
        offer=items[code]
        play=PLAYBOOK[code]
        packages.append({
            "offer_code":code,
            "buyer_type":play["buyer_type"],
            "commercial_track":play["commercial_track"],
            "one_line_value":play["one_line_value"],
            "proposed_delivery":play["proposed_delivery"],
            "price_hypothesis":dict(offer["price_hypothesis"]),
            "pilot_capacity_promise_authorized":False,
            "source_product_id":offer["existing_product_id"],
            "owner_lane":play["sales_owner_lane"],
            "delivery_owner_lane":play["delivery_owner_lane"],
            "proof_needed_before_binding_offer":list(play["minimum_evidence"]),
            "report_examples_are_private_not_customer_fulfilment":True,
            "no_current_rank_or_traffic_automatically_inferred":True,
            "customer_contract_verified":False,
            "real_contact_qualified":False,
            "outbound_clearance_verified":False,
            "source_rights_and_licence_signed_off":False,
            "capacity_to_deliver_verified":False,
            "buyer_scope_accepted":False,
            "payment_verified":False,
            "fulfilment_verified":False,
            "commercial_stage":"DRAFT_INTERNAL_NOT_SENT_OR_COMMITTED",
            "customer_entitlement_created":False,
            "live_public_listing":False,
        })
    digest=sha256(json.dumps(
        [{"code":p["offer_code"],"terms":p["price_hypothesis"],
          "proof":p["proof_needed_before_binding_offer"]} for p in packages],
        sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "status":"THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD",
        "assessed_at_utc":moment.astimezone(timezone.utc).isoformat(),
        "mode":"OBSERVE","execution_authority":"NONE",
        "existing_portfolio_schema":PORTFOLIO_SCHEMA,
        "source_product_families":4,
        "catalog_offer_hypotheses":14,
        "draft_package_count":len(packages),
        "packages":packages,
        "package_scope_digest_is_not_signature":digest,
        "recommended_sequence":[
            "REUSE_EXISTING_SPC_RESPONSE_THREAD_NO_DUPLICATE_OUTBOUND",
            "VERIFY_AGENCY_PARTNER_CONTACT_AND_EXPLICIT_PROBLEM",
            "QUALIFY_ENTERPRISE_TERRITORY_DECISION_NEED",
            "ONLY_THEN_NEGOTIATE_EXACT_SCOPE_AND_PRICE",
            "CAPTURE_REAL_DELIVERY_AND_SETTLEMENT_EVIDENCE",
        ],
        "human_decision_or_real_reply_observed_in_this_review":False,
        "no_partner_email_or_personal_contact_fields":True,
        "revenue_amount_recognised":0,
        "forecast_from_unaccepted_offers_enabled":False,
        "source_resale_authorized":False,"data_delivery_authorized":False,
        "outbound_sent":False,"crm_mutation":False,"database_writes":False,
        "payment_activated":False,"external_marketplace_registered":False,
    }

def validate_sales_activation_review(value:Mapping[str,Any])->bool:
    if not isinstance(value,Mapping):
        return False
    if (value.get("schema_version")!=SCHEMA
        or value.get("status")!="THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD"
        or value.get("mode")!="OBSERVE"
        or value.get("execution_authority")!="NONE"
        or value.get("draft_package_count")!=len(SAFE_OFFERS)
        or value.get("catalog_offer_hypotheses")!=14
        or value.get("human_decision_or_real_reply_observed_in_this_review") is not False
        or value.get("forecast_from_unaccepted_offers_enabled") is not False
        or value.get("revenue_amount_recognised")!=0
        or any(value.get(flag) is not False for flag in (
            "source_resale_authorized","data_delivery_authorized",
            "outbound_sent","crm_mutation","database_writes",
            "payment_activated","external_marketplace_registered"))):
        return False
    packages=value.get("packages")
    if type(packages) is not list or len(packages)!=len(SAFE_OFFERS):
        return False
    for p,code in zip(packages,SAFE_OFFERS):
        if not isinstance(p,Mapping) or p.get("offer_code")!=code:
            return False
        if (p.get("commercial_track")!=PLAYBOOK[code]["commercial_track"]
            or p.get("proof_needed_before_binding_offer")!=PLAYBOOK[code]["minimum_evidence"]
            or p.get("proposed_delivery")!=PLAYBOOK[code]["proposed_delivery"]
            or p.get("commercial_stage")!="DRAFT_INTERNAL_NOT_SENT_OR_COMMITTED"
            or p.get("pilot_capacity_promise_authorized") is not False
            or p.get("no_current_rank_or_traffic_automatically_inferred") is not True
            or any(p.get(flag) is not False for flag in (
                "customer_contract_verified","real_contact_qualified",
                "outbound_clearance_verified","source_rights_and_licence_signed_off",
                "capacity_to_deliver_verified","buyer_scope_accepted",
                "payment_verified","fulfilment_verified","customer_entitlement_created",
                "live_public_listing"))):
            return False
        terms=p.get("price_hypothesis")
        if (not isinstance(terms,Mapping)
            or terms.get("buyer_accepted") is not False
            or terms.get("market_price_verified") is not False
            or type(terms.get("amount")) is not int
            or (terms.get("currency"),terms.get("amount"),terms.get("unit"))
                !=EXPECTED_PRICE_HYPOTHESES[code]):
            return False
    return True
