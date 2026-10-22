"""Read-only pre-offer evidence gate for two public B2B requests.

Consumes existing Jev/Buyer Scout and aggregate Lead Supply outputs. Never
identifies a public commenter, exports source records, changes the CRM, sends
messages or interprets an archived record as a deliverable lead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

SCHEMA = "empire.jev.public_b2b_preoffer_review.v1"
UPSTREAM = "empire.jev.b2b_counterparty_readiness.v1"
EXPECTED_IDS = frozenset(("1wciats", "1uk1vw1"))


def _fresh(value: Any, now: datetime, hours: int) -> bool:
    try:
        if not isinstance(value, str):
            return False
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.utcoffset() is None:
            return False
        return timedelta(0) <= now - timestamp.astimezone(timezone.utc) <= timedelta(hours=hours)
    except (TypeError, ValueError, OverflowError):
        return False


def _count(source: Mapping[str, Any], key: str) -> int:
    value = source.get(key)
    if type(value) is not int or not 0 <= value <= 1000000:
        raise ValueError("invalid bounded original aggregate")
    return value


def review_preoffer(
    cases: Mapping[str, Any],
    lead_supply: Mapping[str, Any] | None,
    *,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("review clock must be timezone-aware")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(cases, Mapping)
        or cases.get("schema_version") != UPSTREAM
        or cases.get("mode") != "OBSERVE"
        or cases.get("status") != "TWO_PUBLIC_SUPPLIER_REQUESTS_ORIGINAL_EVIDENCE_GATES_OPEN"
        or not _fresh(cases.get("as_of_utc"), now, 24)
        or cases.get("counterparties_assessed") != 2
        or cases.get("verified_named_buyer_companies") != 0
        or cases.get("current_buying_commitments_verified") != 0
        or cases.get("ready_to_deliver") is not False
        or cases.get("ready_to_contact") is not False
        or cases.get("actual_supply_committed") != 0
        or cases.get("source_licensing_or_contact_consent_verified") is not False
        or cases.get("crm_writes") is not False
        or cases.get("outbound_sent") != 0
        or cases.get("payments_moved") is not False
        or cases.get("execution_authority") != "none"):
        raise ValueError("unverified or promoted upstream counterparty evidence")
    originals = cases.get("cases")
    if (not isinstance(originals, list) or len(originals) != 2
        or {c.get("public_post_id") for c in originals if isinstance(c, Mapping)} != EXPECTED_IDS):
        raise ValueError("wrong bounded public-source case set")
    for item in originals:
        if (not isinstance(item, Mapping)
            or item.get("legal_business_identity_verified") is not False
            or item.get("representative_authority_verified") is not False
            or item.get("current_request_reconfirmed_by_company") is not False
            or item.get("specific_buybox_with_signed_terms_verified") is not False
            or item.get("organic_compliant_source_supply_proven") is not False
            or item.get("source_and_contact_data_rights_verified") is not False
            or item.get("outbound_channel_consent_and_suppression_checked") is not False
            or item.get("available_qualifying_appointments_or_b2b_batches") != 0
            or item.get("crm_prospect_created") is not False
            or item.get("automatic_contact_allowed") is not False):
            raise ValueError("unapproved original commercial case")
    supply_state = "SOURCE_MISSING_OR_STALE"
    totals = {"selected": None, "held_for_evidence": None,
              "waiting_for_buyer_capacity": None, "sellable": None}
    if lead_supply is not None:
        if not isinstance(lead_supply, Mapping):
            raise ValueError("invalid original lead-supply summary")
        if _fresh(lead_supply.get("generated_at"), now, 4):
            mandatory = {
                "state": "FOUNDER_RESEARCH_QUEUE_READY",
                "mode": "READ_ONLY_PRIVATE_LEADGEN",
                "execution_authority": "none",
                "canonical_empiredb_writes": False,
                "buyer_outreach_authorized": False,
                "prospect_insert_authorized": False,
                "public_inventory_claim_allowed": False,
                "territory_matching_performed": False,
                "registry_mailbox_snapshot_fresh": False,
            }
            if any(lead_supply.get(k) != v for k, v in mandatory.items()):
                raise ValueError("original lead-supply authority mismatch")
            if any(_count(lead_supply, key) != 0 for key in (
                "qualified_buyers", "verified_buyer_capacity",
                "ready_for_outbound", "immediately_sellable_inventory")):
                raise ValueError("commercially activated inventory requires an independent contract")
            totals = {
                "selected": _count(lead_supply, "canonical_selected_inventory_records"),
                "held_for_evidence": _count(lead_supply, "canonical_evidence_hold_records"),
                "waiting_for_buyer_capacity": _count(lead_supply, "canonical_capacity_waitlist_records"),
                "sellable": 0,
            }
            if (totals["held_for_evidence"] + totals["waiting_for_buyer_capacity"]
                != totals["selected"]):
                raise ValueError("original inventory holds do not reconcile")
            supply_state = "CURRENT_AGGREGATE_RESEARCH_ONLY_ZERO_SELLABLE"

    plans = [
        {
            "public_case_reference": "1wciats",
            "scope": "TENNESSEE_ROOFING_APPOINTMENTS",
            "model": "TEN_PERCENT_OF_VERIFIED_CLOSED_JOBS",
            "stated_close_based_commission_percent":10,
            "guaranteed_commission_revenue_usd":0,
            "closed_deal_value_verified":False,
            "qualified_appointment_definition_agreed":False,
            "appointment_pilot_ready":False,
            "buyer_company_verified": False,
            "purchase_requirement_current": False,
            "organic_appointment_delivery_proven": False,
            "qualified_appointment_definition_agreed": False,
            "closed_job_attribution_proven": False,
            "payment_terms_and_disputes_agreed": False,
            "next_owner_review": [
                "CONFIRM_DIRECT_COMPANY_DISCLOSURE_AND_CURRENT_DEMAND",
                "VERIFY_ORGANIC_APPOINTMENT_SOURCE_AND_CONSENT",
                "ESTABLISH_ACCEPTED_APPOINTMENT_AND_CLOSED_JOB_AUDIT",
                "CHECK_REFUNDS_DISPUTES_PAYMENT_AND_MARGIN",
                "CHECK_PRIOR_RELATIONSHIP_AND_SUPPRESSION",
            ],
            "proposed_pilot":"ZERO_DELIVERY_INTERNAL_FEASIBILITY_CHECK",
            "commercial_offer_ready":False,
            "contact_authorized":False,
        },
        {
            "public_case_reference": "1uk1vw1",
            "scope":"US_BUSINESS_WEBSITE_STATUS_RESEARCH",
            "model":"FIFTY_ACCEPTED_RECORDS_FOR_USD_150_PLUS_CONTINGENT_COMMISSION",
            "full_batch_record_target":50,
            "gross_payment_per_fully_accepted_batch_usd":150,
            "maximum_stated_gross_base_payment_usd":150,
            "actual_accepted_record_count":0,
            "contract_and_payment_proof":False,
            "company_identity_verified":False,
            "source_reuse_and_contact_purpose_rights_verified":False,
            "business_website_status_independently_checked":False,
            "batch_acceptance_criteria_verified":False,
            "projected_profit_verified":False,
            "next_owner_review":[
                "RECONFIRM_REQUEST_AND_LEGAL_AGENCY",
                "OBTAIN_WRITTEN_BATCH_ACCEPTANCE_AND_PAYMENT_TERMS",
                "REVIEW_LAWFUL_BUSINESS_DATA_SOURCES_AND_PERMITTED_USE",
                "TEST_PRIVATE_NON_CONTACT_SAMPLE_FOR_WEBSITE_STATUS_ACCURACY",
                "MEASURE_RESEARCH_AND_QA_COST_BEFORE_PROMISING_FIFTY_RECORDS",
                "CHECK_PRIOR_RELATIONSHIP_AND_SUPPRESSION",
            ],
            "proposed_pilot":"ZERO_DELIVERY_PRIVATE_SYNTHETIC_QA_DRY_RUN",
            "commercial_offer_ready":False,
            "contact_authorized":False,
        },
    ]
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"B2B_PREOFFER_READINESS_HELD_RESEARCH_ONLY",
        "audit_at_utc":now.isoformat(),
        "lead_supply_status":supply_state,
        "lead_supply_counts":totals,
        "two_public_post_hypotheses_not_two_verified_buyers":True,
        "plans":plans,
        "buyer_company_identifications_verified":0,
        "live_customer_purchase_requests_reconfirmed":0,
        "qualified_organic_deliveries_verified":0,
        "historic_empiredb_records_eligible_for_bulk_sale":0,
        "no_paid_traffic":True,
        "valid_communication_consent_and_suppression_receipt":False,
        "commercial_offers_ready":0,
        "promised_deliveries":0,
        "paid_revenue_verified":False,
        "messages_sent":0,
        "canonical_crm_records_created":0,
        "database_writes":False,
        "execution_authority":"none",
    }
