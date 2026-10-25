"""Original EmpireOS Permit Intelligence controlled Gmail Inbox test evidence.

Accept only founder-owned connector evidence, never a generic prospect
address or claimed spam-avoidance rate. Live observed 2026-10-24:
 connected Workspace Gmail send -> separately connected founder Gmail Inbox,
 original From subdomain, root SMTP MAIL FROM and root aligned DKIM.
 This is ONE independent observed Gmail result, no Outlook or contractor
 measurement; no use of original production GMail relay, no prospect send.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any,Mapping

SCHEMA="empire.permit_data.controlled_founder_gmail_seed_receipt.v1"
SOURCE_SCHEMA="empire.permit_data.private_email_deliverability_preflight.v1"
EXPECTED_SUBJECT="EmpireOS Permit Intelligence — controlled Gmail inbox placement test — 24 Oct 2026"
SENDER_VISIBLE="phil@mail.empire-ai.co.uk"
ENVELOPE_SENDER="phil@empire-ai.co.uk"
CONTROLLED_RECIPIENT="flavag83@gmail.com"

def _hash(d:Mapping[str,Any])->str:
    return sha256(json.dumps(d,sort_keys=True,separators=(",",":"),
                       allow_nan=False).encode()).hexdigest()

def build_controlled_seed_receipt(*,original_audit:Mapping[str,Any],
                                  observed:Mapping[str,Any])->dict:
    if (not isinstance(original_audit,Mapping)
        or original_audit.get("schema_version")!=SOURCE_SCHEMA
        or original_audit.get("private_deliverability_sha256")!=_hash({
            k:v for k,v in original_audit.items() if k!="private_deliverability_sha256"})
        or original_audit.get("total_existing_and_new_company_research_reviewed")!=13
        or original_audit.get("outbound_permitted") is not False
        or original_audit.get("inbox_placement_rate_permit_lane") is not None
        or original_audit.get("outbound_sent") is not False):
        raise ValueError("untrusted_original_permit_mail_audit")
    if not isinstance(observed,Mapping):
        raise ValueError("untrusted_gmail_connected_account_receipt")
    expected_keys={
        "provider","source_connected_gmail_account","recipient_connected_gmail_account",
        "visible_from","smtp_mailfrom","dkim_signing_domain","dmarc_header_from",
        "email_subject","sent_message_id","received_message_id","observed_received_utc",
        "sender_sent_label_present","recipient_inbox_label_present",
        "recipient_spam_label_present","spf_pass","dkim_pass","dmarc_pass",
        "authoritative_received_raw_header_examined","actual_send_completed",
    }
    if (set(observed)!=expected_keys
        or observed.get("provider")!="USER_CONNECTED_GMAIL"
        or observed.get("source_connected_gmail_account")!=ENVELOPE_SENDER
        or observed.get("recipient_connected_gmail_account")!=CONTROLLED_RECIPIENT
        or observed.get("visible_from")!=SENDER_VISIBLE
        or observed.get("smtp_mailfrom")!=ENVELOPE_SENDER
        or observed.get("dkim_signing_domain")!="empire-ai.co.uk"
        or observed.get("dmarc_header_from")!="mail.empire-ai.co.uk"
        or observed.get("email_subject")!=EXPECTED_SUBJECT
        or observed.get("sender_sent_label_present") is not True
        or observed.get("recipient_inbox_label_present") is not True
        or observed.get("recipient_spam_label_present") is not False
        or observed.get("spf_pass") is not True
        or observed.get("dkim_pass") is not True
        or observed.get("dmarc_pass") is not True
        or observed.get("authoritative_received_raw_header_examined") is not True
        or observed.get("actual_send_completed") is not True):
        raise ValueError("gmail_controlled_seed_auth_or_ownership_invalid")
    for key in ("sent_message_id","received_message_id"):
        if not isinstance(observed.get(key),str) or not re.fullmatch(r"[0-9a-f]{16}",observed[key]):
            raise ValueError("gmail_controlled_seed_message_id_invalid")
    if observed["sent_message_id"]==observed["received_message_id"]:
        raise ValueError("cross_account_receipts_should_be_distinct")
    # 14:09 UTC received; independent receiver Gmail label and auth headers.
    if observed.get("observed_received_utc")!="2026-10-24T14:09:01+00:00":
        raise ValueError("controlled_seed_received_clock_mismatch")
    info={
        "schema_version":SCHEMA,
        "mode":"OBSERVED_ONE_CONTROLLED_GMAIL_DELIVERY_NOT_PROSPECT_SEND",
        "original_product":"ONE_EMPIREOS_PERMIT_INTELLIGENCE",
        "original_preflight_sha256":original_audit["private_deliverability_sha256"],
        "evidence_custodian":"USER_CONNECTED_GMAIL_ACCOUNT_RECEIVED_MAIL_AND_RAW_HEADER",
        "provider_evidence_signed_by_original_empiredb_owner":False,
        "observed_received_utc":observed["observed_received_utc"],
        "sender_account":"phil@empire-ai.co.uk",
        "header_visible_from":"phil@mail.empire-ai.co.uk",
        "root_envelope_sender":"phil@empire-ai.co.uk",
        "dkim_signing_domain":"empire-ai.co.uk",
        "dmarc_header_from_domain":"mail.empire-ai.co.uk",
        "spf_pass":True,"dkim_pass":True,"dmarc_pass":True,
        "controlled_gmail_inbox_observed":True,
        "controlled_gmail_spam_observed":False,
        "sent_provider_message_id":observed["sent_message_id"],
        "recipient_provider_message_id":observed["received_message_id"],
        "emails_sent_to_founder_controlled_seed":1,
        "emails_sent_to_actual_prospects":0,
        "actual_permit_prospect_delivery_receipts":0,
        "real_prospect_inbox_placement_rate":None,
        "controlled_test_sample_count":1,
        "controlled_gmail_observed_inbox_count":1,
        "controlled_gmail_seed_success_not_a_population_rate":True,
        "outlook_or_microsoft_seed_tested":False,
        "outlook_inbox_spam_placement":None,
        "original_production_relay_send_authorized":False,
        "original_production_relay_used_for_this_test":False,
        "send_executed_using_connected_gmail_plugin":True,
        "spf_lookup_recursive_budget_still_not_assessed":True,
        "first_wave_recipient_suppression_cleared":0,
        "second_wave_recipient_suppression_cleared":0,
        "customer_sample_shared":False,
        "permit_outreach_approved":False,
        "payment_activated":False,
        "verified_permit_revenue_usd":"0.00",
        "empiredb_writes":0,
        "smart_crm_writes":0,
        "astra_jobs_scheduled":0,
        "execution_authority":"none",
    }
    info["controlled_seed_sha256"]=_hash(info)
    return info


def render_seed(report:Mapping[str,Any])->str:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("controlled_seed_sha256")!=_hash({
            k:v for k,v in report.items() if k!="controlled_seed_sha256"})
        or report.get("mode")!="OBSERVED_ONE_CONTROLLED_GMAIL_DELIVERY_NOT_PROSPECT_SEND"
        or report.get("controlled_gmail_inbox_observed") is not True
        or report.get("emails_sent_to_actual_prospects")!=0
        or report.get("real_prospect_inbox_placement_rate") is not None
        or report.get("outlook_or_microsoft_seed_tested") is not False
        or report.get("original_production_relay_used_for_this_test") is not False
        or report.get("permit_outreach_approved") is not False
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_original_gmail_seed_report")
    return (
        "# EmpireOS Permit Intelligence — controlled Gmail live delivery receipt\n\n"
        "**ONE OWNER-CONTROLLED TEST — NOT PROSPECT MAIL, NOT AN INBOX-PLACEMENT RATE**\n\n"
        "- Sent: 24 October 2026 using the USER-CONNECTED Empire AI Workspace Gmail account to the founder-controlled Gmail inbox.\n"
        "- Visible From: phil@mail.empire-ai.co.uk\n"
        "- Actual envelope sender: phil@empire-ai.co.uk\n"
        "- Receiver Gmail label: INBOX; SPAM absent; actual received message ID recorded in private JSON.\n"
        "- Raw received Authentication-Results: SPF=PASS, DKIM=PASS signing empire-ai.co.uk, DMARC=PASS aligned to mail.empire-ai.co.uk.\n"
        "- Sender Gmail connection completed the send; this did NOT use or activate the separately held EmpireOS production relay.\n"
        "- Independent current Outlook test: NONE. Other ISP/contractor delivery: UNKNOWN.\n"
        "- Current real prospect inbox-rate: UNKNOWN (null), not an estimate from 1 controlled success.\n"
        "- 13 researched contractors, zero recipient-level suppressions cleared, zero prospect emails sent.\n"
        "- Required next: real separately controlled Microsoft seed, exact authorised send, read actual Inbox/Junk and raw headers; then per-recipient owner CRM review.\n"
        "- No data products distributed, new DB/CRM writes, DNS changes, schedule, checkout or payments.\n"
    )
