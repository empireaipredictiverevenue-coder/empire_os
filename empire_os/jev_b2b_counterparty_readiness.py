"""Original B2B supplier requests → buyer/company and delivery readiness.

Reuses the existing Jev public-source candidate contract and canonical
Buyer Scout reader. This is an evidence gap dossier, NEVER a substitute for
the Research owner, CRM identity gate, an accepted sale or organic delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.executive_buyer_capacity_review import review_buyer_capacity
from empire_os.jev_external_public_need_review import review_public_b2b_needs

SCHEMA="empire.jev.b2b_counterparty_readiness.v1"
FOCAL=("1wciats","1uk1vw1")
ORIGINAL_PUBLIC_EVIDENCE={
    "1wciats":{
        "business_type":"ROOFING_COMPANY_SELF_REPORTED",
        "region":"Knoxville, Tennessee, USA",
        "public_corroboration":"POST_AUTHOR_PUBLICLY_DESCRIBES_RECRUITING_ROOFING_SALES_REPS_KNOXVILLE",
        "corroboration_url":"https://www.reddit.com/r/RoofingSales/comments/1wb5rly/roofing_sales_reps_position/",
        "commercial_model":"COMMISSION_ON_CLOSED_BOOKED_ROOFING_APPOINTMENTS",
        "stated_terms":"TEN_PERCENT_CLOSED_DEAL_NO_UPFRONT_FEE",
        "required_service":"ORGANIC_VERIFIED_ROOFING_APPOINTMENT_DELIVERY",
        "source_proves_named_company":False,
        "source_proves_active_buyer":False,
    },
    "1uk1vw1":{
        "business_type":"US_WEB_AGENCY_SELF_REPORTED",
        "region":"US, city unspecified",
        "public_corroboration":"REDDIT_PROFILE_DOES_NOT_PUBLICLY_ESTABLISH_LEGAL_AGENCY_IDENTITY",
        "corroboration_url":"https://www.reddit.com/user/sine-si/",
        "commercial_model":"ACCEPTED_LOCAL_BUSINESS_RESEARCH_BATCHES_PLUS_CLOSED_DEAL_COMMISSION",
        "stated_terms":"USD_150_PER_ACCEPTED_50_LEADS_PLUS_TEN_PERCENT_PAID_CLOSE",
        "required_service":"LAWFUL_BUSINESS_ONLY_RESEARCH_PROVENANCE_AND_WEBSITE_STATUS",
        "source_proves_named_company":False,
        "source_proves_active_buyer":False,
    },
}


def _verify_routing(routing:Mapping[str,Any]|None)->dict[str,Any]:
    # Ringba evidence concerns a *different* Chicago pilot; it must not
    # be misrepresented as confirmation of Knoxville organic supply.
    if not isinstance(routing,Mapping):
        return {"chicago_pilot_routing_evidence":"UNAVAILABLE",
                "proof_of_tennessee_organic_supply":False}
    if (routing.get("mode")!="OBSERVE"
        or routing.get("route_mutation_performed") is not False
        or routing.get("test_call_performed") is not False):
        raise ValueError("untrusted routing source authority")
    return {
        "chicago_pilot_routing_evidence":(
            "CONFIG_NOT_PROVEN" if routing.get("routing_runtime_verified") is False
            else "OTHER_MARKET_ROUTE_DOES_NOT_PROVE_ORGANIC_TENNESSEE_SUPPLY"
        ),
        "proof_of_tennessee_organic_supply":False,
    }


def audit_public_b2b_counterparties(
    candidates:Mapping[str,Any],*,buyer_capacity:Mapping[str,Any]|None,
    existing_roofing_route:Mapping[str,Any]|None,as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("exact aware clock needed")
    as_of_utc=as_of.astimezone(timezone.utc)
    from datetime import date
    original=review_public_b2b_needs(candidates,as_of=date(2026,10,22))
    if (original["status"]!="PUBLIC_B2B_NEED_SOURCE_CANDIDATES_RESEARCH_OWNER_REVIEW_ONLY"
        or original["verified_legal_business_buyers"]!=0
        or original["b2b_lead_sales_ready"]!=0
        or original["approved_outbound_messages"]!=0):
        raise ValueError("untrusted original source classifications")
    by_id={r["public_post_id"]:r for r in original["items"]}
    if not all(i in by_id for i in FOCAL):
        raise ValueError("missing initial supplier requests")
    capacity=review_buyer_capacity(buyer_capacity,as_of=as_of_utc)
    if (capacity["execution_authority"]!="none"
        or capacity["specific_buybox_verified"] is not False
        or capacity["lead_delivery_authorized"] is not False
        or capacity["payment_execution"] is not False):
        raise ValueError("upstream Buyer Scout granted authority")
    route=_verify_routing(existing_roofing_route)
    cases=[]
    for ident in FOCAL:
        record=by_id[ident]
        public=ORIGINAL_PUBLIC_EVIDENCE[ident]
        if (record["original_business_identity_verified"] is not False
            or record["buyer_authority_verified"] is not False
            or record["valid_consent_to_contact_verified"] is not False
            or record["commercial_terms_verified"] is not False
            or record["current_demand_confirmed"] is not False
            or record["outreach_authorized"] is not False):
            raise ValueError("public request unexpectedly approved")
        verification_tasks=[
            "SOURCE_OWNER_REVERIFY_UNEDITED_ORIGINAL_POST_AND_CURRENT_REQUEST",
            "REQUIRE_BUSINESS_DIRECT_SELF_DISCLOSURE_AND_LEGAL_ENTITY_MATCH",
            "CONFIRM_REPRESENTATIVE_BUYING_AUTHORITY_AND_TERMS",
            "CHECK_ORGANIC_SUPPLY_FEASIBILITY_AND_DOCUMENT_ACCEPTANCE_CRITERIA",
            "RECONCILE_EXISTING_TENANT_CRM_THREAD_AND_SUPPRESSION_BEFORE_OUTREACH",
        ]
        if ident=="1wciats":
            verification_tasks.insert(3,
                "VERIFY_CLOSED_DEAL_ATTRIBUTION_MARGIN_DISPUTE_AND_COMMISSION_PAYMENT_RULES")
            stage="TERMS_REVIEW_IDENTITY_AND_ORGANIC_APPOINTMENT_PROOF_REQUIRED"
        else:
            verification_tasks.insert(3,
                "VERIFY_BUSINESS_ONLY_DATA_USAGE_PHONE_FIELD_RIGHTS_WEBSITE_STATUS_AND_BATCH_ACCEPTANCE")
            stage="STALE_REQUEST_AND_BUSINESS_DATA_RIGHTS_REVALIDATION_REQUIRED"
        cases.append({
            "public_post_id":ident,
            "original_public_post_url":record["source_url"],
            "self_reported_business_type":public["business_type"],
            "claimed_business_region":public["region"],
            "public_context_status":public["public_corroboration"],
            "public_context_source_url":public["corroboration_url"],
            "commercial_model":public["commercial_model"],
            "self_stated_terms":public["stated_terms"],
            "required_service":public["required_service"],
            "current_request_reconfirmed_by_company":False,
            "legal_business_identity_verified":False,
            "representative_authority_verified":False,
            "specific_buybox_with_signed_terms_verified":False,
            "organic_compliant_source_supply_proven":False,
            "available_qualifying_appointments_or_b2b_batches":0,
            "source_and_contact_data_rights_verified":False,
            "outbound_channel_consent_and_suppression_checked":False,
            "revenue_share_attribution_or_batch_acceptance_verified":False,
            "feasibility_status":stage,
            "next_owner_checks":verification_tasks,
            "automatic_contact_allowed":False,
            "crm_prospect_created":False,
            "proposal_ready":False,
            "payment_expected_recognised":False,
        })
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"TWO_PUBLIC_SUPPLIER_REQUESTS_ORIGINAL_EVIDENCE_GATES_OPEN",
        "as_of_utc":as_of_utc.isoformat(),
        "public_source_posts_reviewed":len(original["items"]),
        "counterparties_assessed":len(cases),
        "self_declared_business_purchase_requests":len(cases),
        "verified_named_buyer_companies":0,
        "current_buying_commitments_verified":0,
        "buyer_scout_aggregate_status":capacity["status"],
        "buyer_scout_aggregate_counts":capacity["counts"],
        "buyer_scout_is_not_supplier_inventory_proof":True,
        "existing_other_market_roofing_route":route,
        "cases":cases,
        "actual_supply_committed":0,
        "source_licensing_or_contact_consent_verified":False,
        "ready_to_deliver":False,
        "ready_to_contact":False,
        "crm_writes":False,
        "outbound_sent":0,
        "payments_moved":False,
        "execution_authority":"none",
    }
