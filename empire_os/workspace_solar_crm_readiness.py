"""Combine the three EXISTING private Founder read endpoints for CRM review.

Only previously documented, bounded six-company metadata. No DB connection,
new timer, sender, contact addresses, body, public route or CRM writes.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.workspace_solar_reply_tracking import ANCHORS

SCHEMA="empire.workspace_solar_crm_readiness.v1"
COMPANIES={a[0] for a in ANCHORS}
HIST_SCHEMA="empire.workspace_historical_receipt_admission_status.v1"
CANONICAL_SCHEMA="empire.workspace_solar_canonical_intent_review.v1"
GMAIL_SCHEMA="empire.founder_workspace_reply_review.v1"


class CRMReadinessHeld(ValueError):
    """Cannot safely infer CRM readiness from incomplete source observations."""


def _six_rows(doc: Mapping[str, Any], label: str) -> dict[str, Mapping[str, Any]]:
    items=doc.get("items")
    if not isinstance(items,list) or len(items)!=6:
        raise CRMReadinessHeld(label+"_COUNT_INVALID")
    by_company={}
    for item in items:
        if not isinstance(item,Mapping):
            raise CRMReadinessHeld(label+"_ROW_INVALID")
        company=item.get("company")
        if not isinstance(company,str) or company not in COMPANIES or company in by_company:
            raise CRMReadinessHeld(label+"_COMPANY_DRIFT")
        by_company[company]=item
    if set(by_company)!=COMPANIES:
        raise CRMReadinessHeld(label+"_COMPANY_COVERAGE_MISSING")
    return by_company


def combine_six_company_crm_readiness(
    historical: Mapping[str,Any],
    canonical: Mapping[str,Any],
    gmail: Mapping[str,Any],
) -> dict[str,Any]:
    if not all(isinstance(x,Mapping) for x in (historical,canonical,gmail)):
        raise CRMReadinessHeld("SOURCE_OBJECT_MISSING")
    if (
        historical.get("schema_version")!=HIST_SCHEMA
        or historical.get("status")!="SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB"
        or historical.get("database_historical_receipts_verified")!=6
        or historical.get("private_custody_receipts_verified")!=6
        or historical.get("database_historical_receipt_table_active") is not True
        or historical.get("mode")!="OBSERVE"
        or historical.get("crm_handoff_authorized") is not False
        or historical.get("crm_records_created")!=0
        or historical.get("canonical_outbound_intents_created")!=0
        or historical.get("historical_approvals_backfilled")!=0
        or historical.get("outbound_sent") is not False
        or historical.get("database_writes") is not False
    ):
        raise CRMReadinessHeld("HISTORICAL_EVIDENCE_NOT_VERIFIED")
    if (
        canonical.get("schema_version")!=CANONICAL_SCHEMA
        or canonical.get("status")!="CANONICAL_INTENT_AGGREGATES_REVIEW_ONLY"
        or canonical.get("threads_checked")!=6
        or canonical.get("exact_recipient_scan_complete") is not True
        or canonical.get("mode")!="OBSERVE"
        or canonical.get("crm_mutation") is not False
        or canonical.get("outbound_sent") is not False
        or canonical.get("founder_crm_delivery_verified") is not False
    ):
        raise CRMReadinessHeld("CANONICAL_READER_EVIDENCE_INCOMPLETE")
    if (
        gmail.get("schema_version")!=GMAIL_SCHEMA
        or gmail.get("status")!="FRESH_WORKSPACE_REVIEW_QUEUE"
        or gmail.get("mode")!="OBSERVE"
        or gmail.get("monitored_threads")!=6
        or gmail.get("sent_anchors_verified")!=6
        or type(gmail.get("inbound_header_candidate_count")) is not int
        or not 0 <= gmail["inbound_header_candidate_count"] <= 474
        or gmail.get("crm_conversation_created") is not False
        or gmail.get("crm_mutation") is not False
        or gmail.get("outbound_sent") is not False
        or gmail.get("crm_identity_and_tenant_unverified") is not True
    ):
        raise CRMReadinessHeld("GMAIL_REVIEW_NOT_VERIFIED")
    hist=_six_rows(historical,"HISTORICAL")
    canon=_six_rows(canonical,"CANONICAL")
    emails=_six_rows(gmail,"GMAIL")
    results=[]
    candidate_count=0
    for company in sorted(COMPANIES):
        h,c,g=hist[company],canon[company],emails[company]
        if (
            h.get("original_sent_receipt_custody_verified") is not True
            or h.get("empiredb_historical_evidence_admitted") is not True
            or h.get("status")!="UNBOUND_HISTORICAL_EVIDENCE_IN_EMPIREDB"
            or h.get("canonical_sent_intent_created") is not False
            or h.get("historical_approval_verified") is not False
            or h.get("crm_contact_bound") is not False
            or h.get("commercial_revenue_verified") is not False
            or g.get("sent_verified") is not True
            or g.get("crm_conversation_created") is not False
            or g.get("tenant_and_contact_binding_verified") is not False
            or c.get("crm_handoff_authorized") is not False
            or c.get("canonical_contact_verified") is not False
            or c.get("tenant_identity_verified") is not False
            or c.get("historical_send_reconciliation_automatically_authorized") is not False
            or c.get("recipient_only_evidence_is_not_original_send_linkage") is not True
        ):
            raise CRMReadinessHeld("UNAUTHORISED_HISTORICAL_OR_CONTACT_PROMOTION")
        inbound=g.get("inbound_candidate_count")
        if type(inbound) is not int or not 0 <= inbound <= 79:
            raise CRMReadinessHeld("INVALID_COMPANY_CANDIDATE_COUNT")
        candidate_rows=g.get("inbound_candidates")
        if not isinstance(candidate_rows,list) or len(candidate_rows)!=inbound:
            raise CRMReadinessHeld("INBOUND_COUNT_MISMATCH")
        for candidate in candidate_rows:
            if not isinstance(candidate,Mapping) or candidate.get("crm_handoff_authorized") is not False or candidate.get("commercial_intent_verified") is not False or candidate.get("contact_identity_verified") is not False:
                raise CRMReadinessHeld("UNTRUSTED_INBOUND_AUTHORITY")
        counts=(
            c.get("canonical_same_thread_intents_visible"),
            c.get("canonical_same_recipient_intents_visible"),
            c.get("canonical_exact_recipient_sent_intents_visible"),
            c.get("canonical_approval_rows_visible"),
            c.get("original_sent_provider_message_id_matches"),
        )
        if any(type(n) is not int or n < 0 for n in counts):
            raise CRMReadinessHeld("CANONICAL_LINK_COUNTER_UNVERIFIED")
        thread,recipient,exact_sent,approved,provider=counts
        if exact_sent > thread or provider > exact_sent or approved > exact_sent:
            raise CRMReadinessHeld("CANONICAL_LINK_COUNTER_CONTRADICTION")
        canonical_next=c.get("next_founder_review_action")
        if canonical_next not in (
            "REVIEW_HISTORICAL_SENT_EVIDENCE_FOR_CANONICAL_ADMISSION",
            "REVIEW_POTENTIAL_UNLINKED_EXACT_RECIPIENT_RECORDS",
            "REVIEW_EXACT_ORIGINAL_RECIPIENT_MISMATCH",
            "RESOLVE_CANONICAL_INTENT_AMBIGUITY",
            "VERIFY_ACTUAL_FOUNDER_APPROVAL_PROVENANCE",
            "RECONCILE_ORIGINAL_PROVIDER_MESSAGE_PROVENANCE",
            "VERIFY_TENANT_CONTACT_SUPPRESSION_AND_BUYER_REPLY",
        ):
            raise CRMReadinessHeld("UNKNOWN_CANONICAL_REVIEW_ACTION")
        relation=(
            "NO_CANONICAL_INTENT_VISIBLE_TO_READER"
            if thread==0 and recipient==0
            else "CANONICAL_RECONCILIATION_REQUIRED"
        )
        results.append({
            "company":company,
            "historical_provider_sent_evidence":"VERIFIED_IN_EMPIREDB_UNBOUND",
            "canonical_intent_linkage":relation,
            "canonical_next_review_action":canonical_next,
            "inbound_provider_header_candidates":inbound,
            "inbound_next_review_action":(
                "VERIFY_GENUINE_REPLY_CONTENT_AND_SUPPRESSION"
                if inbound else "WAIT_FOR_GENUINE_BUYER_REPLY"
            ),
            "crm_handoff_status":"NOT_AUTHORISED_REQUIRES_CONTACT_TENANT_AND_REPLY_PROOF",
            "crm_record_created":False,
            "outbound_authorised":False,
        })
        candidate_count+=inbound
    if candidate_count!=gmail["inbound_header_candidate_count"]:
        raise CRMReadinessHeld("AGGREGATE_CANDIDATE_COUNT_CONTRADICTORY")
    return {
        "schema_version":SCHEMA,
        "status":"SIX_COMPANY_HISTORICAL_TO_CRM_GAP_REGISTER_READ_ONLY",
        "mode":"OBSERVE",
        "companies_checked":6,
        "historical_receipts_verified_in_empiredb":6,
        "inbound_provider_header_candidates":candidate_count,
        "canonical_approval_or_contact_proven":False,
        "founder_crm_handoff_authorized":False,
        "crm_records_created":0,
        "emails_sent":False,
        "payments_executed":False,
        "database_writes":False,
        "items":results,
    }
