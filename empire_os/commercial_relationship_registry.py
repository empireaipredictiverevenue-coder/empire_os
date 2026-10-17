"""Fail-closed buyer relationship registry: discovery + Gmail summary + founder holds.

Email content is untrusted evidence, never execution instructions. No SMTP,
mailbox login, DB writes, commercial approval, call routing or outbound.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from empire_os.buyer_review_holds import do_not_pursue_domains as founder_do_not_pursue_domains
from empire_os.buyer_mail_semantics import EVENT_CODES


class RelationshipEvidenceError(ValueError):
    pass


SCHEMA = "empire.buyer_mail_relationship_summary.v1"
OUTPUT_SCHEMA = "empire.commercial_relationship_registry.v1"
HEX_ID = re.compile(r"^[a-f0-9]{12,24}$")
VALID_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")
VALID_DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
ALLOWED_HINTS = {
    "LANDING_APPROVAL_AND_ROUTE_PROOF",
    "ONBOARDING_BUYBOX",
    "REQUEST_BUYER_MARKETS",
    "WAITING_MARKET_DETAILS",
    "REQUEST_CURRENT_BUYBOX",
    "VERIFY_CONTACT_CHANNEL",
    "REVIEW_ONLY",
}
MAX_AGE_SECONDS = 96 * 3600

# Separate prospective buyer corridors. These are founder-proposed scopes based
# on human-reviewed Gmail threads; no cross-buyer terms or tracking is inherited.
PARTNER_PILOT_SCOPES = {
    "leadbank": {
        "corridor": "US_ROOFING_INSTALL_REPLACEMENT_FIRST_PARTY_ORGANIC",
        "reviewed_thread": "1a0cfb65e0dd960e",
        "partner_request_ref": "gmail:1a11902593b62d2c",
        "founder_reply_ref": "gmail:1a11aa2fa91135f0",
        "next_partner_evidence": [
            "active_roofing_zips_and_buyer_markets",
            "accepted_jobs_duration_hours_and_caps",
            "payout_duplicate_dispute_and_settlement_terms",
            "agreement_mva_w8_requirements",
            "mahad_tracking_and_routing_handoff",
        ],
    },
    "validated": {
        "corridor": "US_ROOFING_INSTALL_REPLACEMENT_FIRST_PARTY_ORGANIC",
        "reviewed_thread": "1a0cfb667dca0957",
        "partner_request_ref": "gmail:1a114d6b9b33e40b",
        "founder_reply_ref": "gmail:1a117d5a0e0fb530",
        "next_partner_evidence": [
            "active_roofing_zips_and_buyer_markets",
            "accepted_jobs_and_qualified_billable_event",
            "revenue_share_duplicate_dispute_and_settlement_terms",
            "source_landing_and_consent_approval",
            "tracking_transfer_or_delivery_contract",
        ],
    },
    "inquirly.com": {
        "corridor": "US_NJ_ROOFING_INSTALL_REPLACEMENT_FIRST_PARTY_ORGANIC_REVIEW",
        "reviewed_thread": "1a0d9ef44c7f77d0",
        "partner_request_ref": "gmail:1a130c837466d185",
        "founder_reply_ref": "gmail:1a1313213d12d010",
        "next_partner_evidence": [
            "confirm_live_roofing_buybox_and_current_authoritative_zip_file",
            "approve_07001_to_07005_or_supply_exact_alternative",
            "qualified_payable_call_or_form_event_and_buyer_hours_caps",
            "publisher_source_no_prior_commissions_exemption_and_signed_terms",
            "partner_specific_tracking_routing_recording_consent_and_dedupe",
        ],
    },
    "connexis": {
        "corridor": "UK_OR_US_HOME_SERVICES_FIRST_PARTY_ORGANIC_PROPOSAL",
        "reviewed_thread": "1a0d9fa5b944630a",
        "partner_request_ref": "gmail:1a0e6d76dbe29583",
        "founder_reply_ref": "gmail:1a10922d0223f192",
        "next_partner_evidence": [
            "choose_one_live_uk_or_us_buyer_campaign",
            "active_postcodes_or_zips_and_job_criteria",
            "connected_call_qualification_hours_and_caps",
            "payout_duplicate_dispute_and_settlement_terms",
            "source_review_and_tracking_route_contract",
        ],
    },
}

# Consolidated first-pass information requests ALREADY sent by the founder
# in the original partner threads on 9 October 2026. A source match is only
# evidence that questions were asked; it grants no campaign or send authority.
# Keeping this next to the existing buyer queue prevents agents from
# endlessly re-asking the same list while waiting on real buyer answers.
LAST_CONSOLIDATED_BUYER_REQUEST = {
    "leadbank": "1a122fc6010e3b5b",
    "validated": "1a122fc70c9614c1",
    "connexis": "1a122fc85a098bea",
    "inquirly.com": "1a127a9c44858b8c",
}

SINGLE_PASS_BUYER_QUESTION_GROUPS = (
    "live_buybox_geographies_jobs_hours_caps",
    "accepted_event_duration_quality_duplicates_disputes",
    "payout_settlement_currency_terms",
    "first_party_source_landing_consent_disclosures",
    "route_caller_id_zip_tracking_postbacks_and_test",
    "agreement_tax_onboarding_and_technical_handoff",
)


def single_pass_intake_status(key: str, relationship: Mapping[str, Any]) -> dict[str, Any]:
    """Report proof of a previously sent comprehensive request, never send."""
    expected = LAST_CONSOLIDATED_BUYER_REQUEST[key]
    thread_matches = (
        PARTNER_PILOT_SCOPES[key]["reviewed_thread"]
        in relationship.get("gmail_thread_ids", [])
    )
    source_matches = (
        thread_matches
        and expected == relationship.get("last_outbound_message_id")
        and when(relationship.get("last_outbound_at")) is not None
    )
    # The founder's complete request has an independently reviewed Gmail ID
    # in this precise partner thread. A newer inbound reply or a different
    # latest outbound message must NOT erase that earlier reviewed send.
    # The import itself only proves it when its latest message is the match.
    reviewed_prior_request = thread_matches
    return {
        "schema_version": "empire.partner_single_pass_intake_status.v1",
        "question_groups": list(SINGLE_PASS_BUYER_QUESTION_GROUPS),
        "past_full_information_request_proven_in_import": source_matches,
        "past_full_request_known_from_reviewed_history": reviewed_prior_request,
        "repeat_full_request_blocked": True,
        "repeat_block_reason": (
            "PRIOR_COMPLETE_REQUEST_IN_REVIEWED_THREAD"
            if reviewed_prior_request else "BUYER_THREAD_HISTORY_NOT_RECONCILED"
        ),
        "last_full_request_evidence_ref": (
            "gmail:" + expected if reviewed_prior_request else None
        ),
        "next_action": (
            "WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"
            if reviewed_prior_request else "RECONCILE_EXISTING_EMAIL_HISTORY_BEFORE_ASKING"
        ),
        "source_mailbox": "flavag83@gmail.com",
        "source_snapshot_fresh": relationship.get("gmail_snapshot_fresh") is True,
        "buyer_buybox_verified": False,
        "buyer_terms_verified": False,
        "answer_complete": False,
        "outbound_authorized": False,
        "contract_authorized": False,
        "traffic_authorized": False,
        "execution_authority": "NONE",
    }


# Later Lead Smart correspondence is separately reviewed and already sent.
# This is a SCOPED DELTA (not the original complete onboarding pack) and
# must never be misreported as proof of a connected buyer call or clean ANI.
LEAD_SMART_PENDING_TECHNICAL_REQUEST = {
    "entity_key": "lead-smart",
    "reviewed_thread": "1a0d9ce883c87d4a",
    "last_scoped_request_ref": "gmail:1a12d47934923a1d",
    "buyer_latest_answer_ref": "gmail:1a12d44d7e2f46a8",
    "outstanding_question_groups": [
        "enabled_direct_buyer_destination_and_original_ani",
        "recording_disabled_for_pilot_or_actual_notice_access_retention_deletion",
    ],
}


def reviewed_request_duplicate_guard(
    key: str, relationship: Mapping[str, Any],
) -> dict[str, Any]:
    """Prevent duplicate full questionnaires and a second Lead Smart delta.

    A verified thread binding and previous human-reviewed Gmail message are
    required. Stale imports do not become fresh. Unknown threads are HELD
    pending review, not presumed eligible for new messaging.
    """
    threads = relationship.get("gmail_thread_ids")
    if not isinstance(threads, (list, tuple, set, frozenset)):
        threads = ()
    # New engagements do not need hand-coded message IDs. Use a bounded,
    # authenticated Gmail SENT event discovered by the existing reader.
    all_events = relationship.get("buyer_signal_events", [])
    if not isinstance(all_events, list):
        all_events = []
    eligible = [
        item for item in all_events if isinstance(item, Mapping)
        and item.get("direction") == "outbound"
        and item.get("evidence_grade") == "EMAIL_REPORTED_UNVERIFIED"
        and item.get("event_code") in (
            "COMPLETE_BUYER_REQUIREMENTS_SENT", "PILOT_TECHNICAL_REQUIREMENTS_SENT",
        )
        and isinstance(item.get("message_id"), str)
        and HEX_ID.fullmatch(item["message_id"])
    ]
    eligible.sort(key=lambda item: (item.get("observed_at") or "", item["message_id"]))
    recognized = (
        next((item for item in reversed(eligible)
              if item["event_code"]=="PILOT_TECHNICAL_REQUIREMENTS_SENT"),None)
        if key == "lead-smart"
        else next((item for item in reversed(eligible)
                   if item["event_code"]=="COMPLETE_BUYER_REQUIREMENTS_SENT"),None)
    )
    if recognized is not None:
        ref="gmail:"+recognized["message_id"]
        return {
            "schema_version":"empire.buyer_requirements_duplicate_guard.v1",
            "status": (
                "SPECIFIC_ROUTING_RECORDING_REQUEST_ALREADY_SENT"
                if key=="lead-smart" else "PRIOR_FULL_REQUEST_SENT"
            ),
            "repeat_full_request_allowed":False,
            "request_provenance":ref,
            "outstanding_buyer_questions": (
                list(LEAD_SMART_PENDING_TECHNICAL_REQUEST["outstanding_question_groups"])
                if key=="lead-smart" else list(SINGLE_PASS_BUYER_QUESTION_GROUPS)
            ),
            "last_outbound_is_independent_proof_of_send": (
                recognized["message_id"] == relationship.get("last_outbound_message_id")
            ),
            "source_snapshot_fresh":relationship.get("gmail_snapshot_fresh") is True,
            "buyer_answer_complete":False,"outbound_authorized":False,
            "execution_authority":"NONE",
        }
    if key in PARTNER_PILOT_SCOPES:
        spec = PARTNER_PILOT_SCOPES[key]
        match = spec["reviewed_thread"] in threads
        ref = "gmail:" + LAST_CONSOLIDATED_BUYER_REQUEST[key] if match else None
        outstanding = list(SINGLE_PASS_BUYER_QUESTION_GROUPS) if match else []
        stage = "PRIOR_FULL_REQUEST_SENT" if match else "THREAD_RECONCILIATION_REQUIRED"
    elif key == LEAD_SMART_PENDING_TECHNICAL_REQUEST["entity_key"]:
        spec = LEAD_SMART_PENDING_TECHNICAL_REQUEST
        match = spec["reviewed_thread"] in threads
        ref = spec["last_scoped_request_ref"] if match else None
        outstanding = list(spec["outstanding_question_groups"]) if match else []
        stage = "SPECIFIC_ROUTING_RECORDING_REQUEST_ALREADY_SENT" if match else "THREAD_RECONCILIATION_REQUIRED"
    else:
        return {
            "schema_version": "empire.buyer_requirements_duplicate_guard.v1",
            "status": "UNREVIEWED_RELATIONSHIP",
            "repeat_full_request_allowed": False,
            "request_provenance": None,
            "outstanding_buyer_questions": [],
            "outbound_authorized": False,
            "execution_authority": "NONE",
        }
    return {
        "schema_version": "empire.buyer_requirements_duplicate_guard.v1",
        "status": stage,
        "repeat_full_request_allowed": False,
        "request_provenance": ref,
        "outstanding_buyer_questions": outstanding,
        "last_outbound_is_independent_proof_of_send": (
            bool(match) and ref == "gmail:" + str(
                relationship.get("last_outbound_message_id") or ""
            )
        ),
        "source_snapshot_fresh": relationship.get("gmail_snapshot_fresh") is True,
        "buyer_answer_complete": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
    }


# First-party reviewed incoming email. A promise to send documents does NOT
# create signed/received terms or convert a buyer into an activated account.
PARTNER_REVIEWED_RESPONSE_EVIDENCE = {
    "leadbank": {
        "inbound_message_id": "1a1230003eb39320",
        "gmail_thread_id": "1a0cfb65e0dd960e",
        "observed_at": "2026-10-09T23:29:13Z",
        "agreement_and_onboarding_form_promised": True,
        "mahad_technical_questions_forwarded": True,
        "agreement_received": False,
        "commercial_buybox_received": False,
        "buyer_routing_contract_received": False,
        "buyer_markets_and_payout_verified": False,
    }
}


# Independently viewed official public pages are evidence of a *general*
# advertised programme only. They are NOT a current campaign buy-box,
# individually offered payout, accepted contract or granted API permission.
PARTNER_PUBLIC_PROGRAMME_REFERENCES = {
    "inquirly.com": (
        {
            "source": "https://inquirly.com/affiliate-category-coverage/",
            "checked_date": "2026-10-12",
            "reference_type": "PUBLIC_ROOFING_PROGRAMME_AND_COVERAGE",
            "public_observation": "The public roofing calls and form-lead ZIP downloads contain different row counts from the webpage summary; five NJ ZIPs overlap with separate historical Empire roofing observations.",
            "not_corroborated": "Currently enabled buyer capacity, active accepted ZIPs, specific source approval, payable per-call rate, signed commercial terms, commission history or working route.",
            "next_question": "Which roofing ZIP dataset is currently authoritative and may we propose first-party consumer-initiated replacement/installation enquiries for NJ ZIPs 07001–07005?",
        },
    ),
    "leadbank": (),
    "validated": (
        {
            "source": "https://validatedlg.ai/affiliate-agreement",
            "checked_date": "2026-10-10",
            "reference_type": "PUBLIC_AFFILIATE_AGREEMENT",
            "public_observation": "Owned or approved acquisition sources, valid compensable transactions, sub-affiliate restrictions and possible payout offsets require campaign-specific review.",
            "not_corroborated": "Signed/accepted contract or approved roofing buy-box.",
            "next_question": "Which affiliate agreement, campaign insertion order, traffic-source rules, payout and technical setup apply to Empire AI's first-party organic roofing pilot?",
        },
        {
            "source": "https://validatedlg.ai/capabilities",
            "checked_date": "2026-10-10",
            "reference_type": "PUBLIC_ACQUISITION_FORMAT_DESCRIPTION",
            "public_observation": "Public formats include pay-per-call, live transfers and first-party forms with per-buyer attribution and routing requirements.",
            "not_corroborated": "Current roofing buyer market, campaign eligibility or an actual assigned route.",
            "next_question": "Confirm that our first pilot is pay-per-call rather than form/API lead delivery, with exact payable-event and geo/hours requirements.",
        },
    ),
    "connexis": (
        {
            "source": "https://connex.is/pay-per-call",
            "checked_date": "2026-10-10",
            "reference_type": "PUBLIC_PAY_PER_CALL_PROGRAMME",
            "public_observation": "The public live-call marketplace describes per-campaign, duration-based billing and weekly Friday publisher payouts without a minimum.",
            "not_corroborated": "Empire AI's accepted call payout, threshold, campaign, assigned number or signed terms.",
            "next_question": "Is Empire AI being offered the pay-per-call publisher programme, and if so what are the verified call duration, source/consent, caps, route and payout conditions?",
        },
        {
            "source": "https://connex.is/legal/terms-publisher",
            "checked_date": "2026-10-10",
            "reference_type": "PUBLIC_API_CPL_PUBLISHER_TERMS",
            "public_observation": "The separate API lead-publisher terms describe a default 90% share of accepted CPL, 7-day duplicate rule, recorded consent and a £50 weekly withdrawal minimum.",
            "not_corroborated": "Applicability to live calls, individual accepted contract, specific lead/call pricing or source permission.",
            "next_question": "Do the API/CPL terms apply at all to our live-call pilot, and which programme's withdrawal minimum, rev-share or payout schedule actually governs the deal?",
        },
    ),
}


def partner_technical_review_packet(
    key: str, spec: Mapping[str, Any], record: Mapping[str, Any],
) -> dict[str, Any]:
    """Proposed, isolated pilot specification; NOT any existing buyer route.

    This preserves the offer/setup questions while remaining null for every
    field whose value requires explicit buyer or provider evidence.
    """
    doc = PARTNER_REVIEWED_RESPONSE_EVIDENCE.get(key)
    linked = bool(
        doc and record.get("last_inbound_message_id") == doc["inbound_message_id"]
        and doc["gmail_thread_id"] in record.get("gmail_thread_ids", [])
    )
    evidence = dict(doc) if linked else None
    return {
        "schema_version": "empire.partner_technical_review_packet.v1",
        "entity_key": key,
        "status": "REVIEW_ONLY",
        "proposed_campaign_scope_not_accepted": spec["corridor"],
        "owned_first_party_organic_source_proposed": True,
        "traffic_source_accepted_by_buyer": False,
        "company_site_source": "https://empire-ai.co.uk",
        "external_buyer_program_id": None,
        "verified_target_zips_or_postcodes": None,
        "verified_eligible_job_types": None,
        "verified_buyer_hours_timezone": None,
        "verified_daily_cap": None,
        "verified_billable_event": None,
        "verified_payout_and_settlement": None,
        "approved_consumer_disclosures": None,
        "signed_agreement_evidence": None,
        "proposed_landing_review_asset": (
            f"review-only://partner-pilot/{key}/landing"
        ),
        "landing_page_created_or_published": False,
        "partner_tracking_number": None,
        "partner_tracking_campaign_id": None,
        "routing_provider_selected": None,
        "routing_destination_or_sip_endpoint": None,
        "caller_id_passthrough_test_verified": False,
        "routing_runtime_test_verified": False,
        "buyer_commercial_source_evidence": evidence,
        "official_public_programme_references": [
            dict(x) for x in PARTNER_PUBLIC_PROGRAMME_REFERENCES[key]
        ],
        "general_public_programme_bound_to_this_account": False,
        "applicable_payout_model_confirmed_by_partner": False,
        "selected_partner_offer_format": None,
        # Two independent revenue formats. A public affiliate page or a
        # call-buyer reply cannot authorize consumer form capture or API
        # delivery. Existing legacy SQLite PPL paths are not canonical.
        "publisher_format_review": {
            "status": "BOTH_FORMATS_PROPOSED_NOT_BUYER_APPROVED",
            "PAY_PER_CALL": {
                "partner_specific_offer_confirmed": False,
                "billable_call_duration_and_rules": None,
                "verified_number_and_route": False,
                "live_call_traffic_enabled": False,
            },
            "PAY_PER_LEAD": {
                "partner_specific_offer_confirmed": False,
                "lead_price_exclusive_or_shared_terms": None,
                "accepted_lead_and_duplicate_rules": None,
                "approved_lead_field_and_api_contract": None,
                "consumer_disclosure_and_consent_approved": False,
                "canonical_empiredb_consumer_intake_verified": False,
                "buyer_acceptance_and_rejection_receipts_verified": False,
                "live_form_capture_enabled": False,
                "lead_delivery_enabled": False,
            },
            "cross_format_same_consumer_deduplication_verified": False,
            "double_monetization_authorized": False,
            "launch_authorized": False,
        },
        "contract_signing_channel_confirmed": False,
        "web_or_portal_acceptance_authorized": False,
        "lead_smart_route_or_number_inherited": False,
        "buyer_commercial_terms_inherited": False,
        "traffic_enabled": False,
        "payment_instructions_created": False,
        "actual_revenue": False,
        "contract_signing_authorized": False,
        "execution_authority": "NONE",
    }


# Evidence from reviewed *inbound* Gmail messages only. Never use this
# observation record to create contacts, accept terms or open live routes.
PARTNER_REPORTED_FIELDS = frozenset({
    "programme_format", "buyer_market_coverage", "eligible_jobs",
    "qualified_billable_event", "buyer_operating_hours",
    "buyer_payout_and_settlement", "source_or_disclosure_rules",
    "tracking_and_routing_instructions", "agreement_or_form_details",
})


def attach_partner_inbound_requirements(
    report: dict[str, Any], observed: Mapping[str, Any],
) -> dict[str, Any]:
    """Admit reviewed email claims into EXISTING partner technical packets.

    Email-reported claims are NOT verified commercial requirements. The
    nine independent launch gates, payouts, route and signing authority
    are intentionally unchanged. Exact latest Gmail message bindings
    prevent attachment to stale, spoofed or unrelated buyer threads.
    """
    if (not isinstance(observed, Mapping)
            or observed.get("schema_version") != "empire.partner_inbound_requirements.v1"
            or observed.get("origin") != "connected_gmail_explicit_review"):
        raise RelationshipEvidenceError("invalid_inbound_requirement_provenance")
    items = observed.get("observations")
    if not isinstance(items, list) or len(items) > len(PARTNER_PILOT_SCOPES):
        raise RelationshipEvidenceError("invalid_partner_requirement_count")
    by_partner = {row["entity_key"]: row for row in report["partner_pilot_readiness_queue"]}
    by_relationship = {row["entity_key"]: row for row in report["relationships"]}
    if not by_partner.keys() <= PARTNER_PILOT_SCOPES.keys():
        raise RelationshipEvidenceError("unrecognized_partner_pilot")
    matched = set()
    for item in items:
        if not isinstance(item, Mapping) or set(item) != {
            "entity_key", "gmail_thread_id", "inbound_message_id",
            "reviewed_at", "reported_fields",
        }:
            raise RelationshipEvidenceError("invalid_reported_terms_shape")
        key = item["entity_key"]
        if not isinstance(key, str) or key not in by_partner or key in matched:
            raise RelationshipEvidenceError("unknown_or_duplicate_partner_terms")
        matched.add(key)
        msg_id = item["inbound_message_id"]
        thread = item["gmail_thread_id"]
        relation = by_relationship[key]
        scope = PARTNER_PILOT_SCOPES[key]
        if (not isinstance(msg_id, str) or not re.fullmatch(r"[0-9a-f]{16,32}", msg_id)
                or thread != scope["reviewed_thread"]
                or thread not in relation["gmail_thread_ids"]):
            raise RelationshipEvidenceError("inbound_terms_unmatched_thread")
        reviewed = when(item["reviewed_at"])
        received = when(relation.get("last_inbound_at"))
        generated = when(report.get("generated_at"))
        if (reviewed is None or generated is None
                or (reviewed - generated).total_seconds() > 300):
            raise RelationshipEvidenceError("inbound_requirement_review_time_invalid")
        same_latest_message = msg_id == relation.get("last_inbound_message_id")
        if same_latest_message and (received is None or reviewed < received):
            raise RelationshipEvidenceError("inbound_requirement_review_before_receipt")
        current = (
            same_latest_message and relation.get("gmail_snapshot_fresh") is True
            and (generated - reviewed).total_seconds() <= 96 * 3600
        )
        fields = item["reported_fields"]
        if not isinstance(fields, Mapping) or not fields or len(fields) > len(PARTNER_REPORTED_FIELDS):
            raise RelationshipEvidenceError("invalid_reported_requirement_fields")
        if not set(fields) <= PARTNER_REPORTED_FIELDS:
            raise RelationshipEvidenceError("unknown_or_privileged_reported_field")
        if any(not isinstance(v, str) or not v.strip()
               or len(v) > 240 or any(ord(c) < 32 for c in v)
               for v in fields.values()):
            raise RelationshipEvidenceError("invalid_reported_requirement_text")
        pilot = by_partner[key]
        packet = pilot["technical_review_packet"]
        # Populate review-only claims; not verified runtime/policy identity.
        packet["reported_inbound_requirements"] = {
            "source_ref": "gmail:" + msg_id,
            "reviewed_at": reviewed.isoformat(),
            "evidence_grade": (
                "CURRENT_REPORTED_UNVERIFIED" if current
                else "HISTORICAL_REPORTED_UNVERIFIED"
            ),
            "same_as_latest_imported_inbound": same_latest_message,
            "mailbox_snapshot_fresh": relation.get("gmail_snapshot_fresh") is True,
            "fields": dict(sorted(fields.items())),
            "commercial_terms_confirmed": False,
            "agreement_received_or_signed_verified": False,
            "routing_provider_verified": False,
            "founder_activation_authorized": False,
        }
        if current:
            pilot["current_next_partner_task"] = "REVIEW_REPORTED_BUYBOX_AND_AGREEMENT_EVIDENCE"
        pilot["inbound_requirement_field_count"] = len(fields)
        pilot["inbound_requirement_review_status"] = (
            "REPORTED_AWAITING_INDEPENDENT_VERIFICATION" if current
            else "HISTORICAL_REPORTED_REQUIREMENTS_HOLD"
        )
        # No activation stage promotion: changing from a promise to
        # a reported specification must not imply successful onboarding.
    for key, pilot in by_partner.items():
        if key not in matched:
            pilot["inbound_requirement_field_count"] = 0
            pilot["inbound_requirement_review_status"] = "NO_NEW_VERIFIED_GMAIL_OBSERVATION"
            pilot["technical_review_packet"]["reported_inbound_requirements"] = None
    report["partner_inbound_requirements"] = {
        "schema_version": "empire.partner_inbound_requirements_review.v1",
        "mode": "OBSERVE",
        "reported_partner_count": len(matched),
        "current_review_count": sum(
            by_partner[k]["inbound_requirement_review_status"]
            == "REPORTED_AWAITING_INDEPENDENT_VERIFICATION" for k in matched
        ),
        "historical_hold_count": sum(
            by_partner[k]["inbound_requirement_review_status"]
            == "HISTORICAL_REPORTED_REQUIREMENTS_HOLD" for k in matched
        ),
        "reported_field_count": sum(by_partner[k]["inbound_requirement_field_count"] for k in matched),
        "commercial_activation_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
    }
    return report


PARTNER_LAUNCH_GATES = (
    "buyer_buybox_received_and_verified",
    "current_target_geography_verified",
    "buyer_source_approved",
    "buyer_landing_approved",
    "partner_specific_tracking_verified",
    "partner_specific_routing_verified",
    "buyer_payable_event_and_terms_verified",
    "contract_and_compliance_approved",
    "founder_live_traffic_authorized",
)


def partner_pilot_readiness(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Automated founder visibility, never autonomous launch authorisation.

    All downstream contract/technical gates remain false until independently
    evidenced by partner-specific policy and provider/runtime verification.
    Metadata-only Gmail cannot promote these gates.
    """
    found = {r.get("entity_key"): r for r in relationships}
    rows = []
    for key, spec in PARTNER_PILOT_SCOPES.items():
        relationship = found.get(key)
        if not relationship:
            continue
        thread_present = spec["reviewed_thread"] in relationship["gmail_thread_ids"]
        reply_present = bool(relationship.get("last_inbound_message_id"))
        safe_stage = relationship["stage"] not in ("EVIDENCE_HOLD", "DELIVERY_HOLD")
        snapshot_fresh = relationship.get("gmail_snapshot_fresh") is True
        gates = {gate: False for gate in PARTNER_LAUNCH_GATES}
        review_packet = partner_technical_review_packet(key, spec, relationship)
        leadbank_docs_promised = (
            key == "leadbank"
            and review_packet["buyer_commercial_source_evidence"] is not None
        )
        rows.append({
            "entity_key": key,
            "company": relationship["company"],
            "technical_review_packet": review_packet,
            "agreement_and_handoff_promised_not_received": leadbank_docs_promised,
            "current_next_partner_task": (
                "REVIEW_AGREEMENT_AND_MAHAD_SPEC_ON_RECEIPT"
                if leadbank_docs_promised
                else "CLARIFY_CONNEXIS_LIVE_CALLS_VS_API_CPL_TERMS"
                if key == "connexis"
                else "CONFIRM_VALIDATED_AFFILIATE_TERMS_AND_BUYBOX"
                if key == "validated"
                else (
                    "DEFER_INQUIRLY_UNTIL_VERIFIED_TRAFFIC_NO_REPEAT_REQUEST"
                    if (relationship.get("reviewed_buyer_reply_disposition") or {}).get("status")
                    == "PARTNER_REPORTS_NO_PILOT_WITHOUT_ESTABLISHED_TRAFFIC"
                    else "AWAIT_INQUIRLY_NJ_BUYBOX_LANDING_REVIEW_NO_REPEAT"
                )
                if key == "inquirly.com"
                else "WAIT_CURRENT_BUYBOX_AND_SOURCE_APPROVAL"
            ),
            "proposed_corridor_not_buyer_approved": spec["corridor"],
            "reviewed_gmail_thread_id": spec["reviewed_thread"],
            "partner_request_evidence_ref": spec["partner_request_ref"],
            "founder_reply_evidence_ref": spec["founder_reply_ref"],
            "two_way_gmail_thread_observed": (
                thread_present and reply_present and safe_stage
            ),
            "mailbox_snapshot_fresh": snapshot_fresh,
            "relationship_stage": relationship["stage"],
            "partner_requirement_evidence_requested": spec["next_partner_evidence"],
            "single_pass_buyer_intake": single_pass_intake_status(key, relationship),
            "activation_gates": gates,
            "gate_count_verified": 0,
            "gate_count_total": len(gates),
            "activation_stage": (
                "ONBOARDING_DOCUMENTS_AND_TECH_HANDOFF_PROMISED"
                if leadbank_docs_promised and snapshot_fresh
                else "DEFERRED_PENDING_ESTABLISHED_TRAFFIC"
                if (relationship.get("reviewed_buyer_reply_disposition") or {}).get("status")
                == "PARTNER_REPORTS_NO_PILOT_WITHOUT_ESTABLISHED_TRAFFIC"
                else "WAITING_BUYER_BUYBOX"
                if thread_present and reply_present and snapshot_fresh and safe_stage
                else "REVIEW_RELATIONSHIP_EVIDENCE"
            ),
            "isolated_buyer_route_required": True,
            "lead_smart_route_and_terms_reused": False,
            "contract_signing_authorized": False,
            "tracking_or_route_mutation_performed": False,
            "live_traffic_authorized": False,
            "outbound_authorized": False,
            "execution_authority": "NONE",
        })
    return rows

def _apply_reviewed_request_to_action(
    key: str, guard: Mapping[str, Any],
    *, current_action: str, current_reason: str,
    current_review_required: bool,
) -> tuple[str, str, bool]:
    """Keep the founder queue aligned with previously reviewed buyer email.

    Never turn an old 'request info / landing approval' hint into permission
    for an identical send. Leave suppression/hold and mailbox-freshness
    decisions intact; only replace known obsolete partner-action prompts.
    """
    if not guard.get("request_provenance"):
        return current_action, current_reason, current_review_required
    if key == "lead-smart":
        if current_action == "REVIEW_BUYER_LANDING_APPROVAL_AND_ROUTE":
            return ("REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",
                    "SCOPED_BUYER_REQUEST_ALREADY_SENT", True)
        if current_action == "WAIT_BUYER_RESPONSE":
            return ("WAIT_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",
                    "SCOPED_BUYER_REQUEST_ALREADY_SENT", False)
    if key in PARTNER_PILOT_SCOPES and current_action == "REVIEW_PENDING_BUYER_REQUEST":
        return ("REVIEW_ANSWERED_FIELDS_ONLY_NO_REPEAT_QUESTIONNAIRE",
                "COMPLETE_BUYER_REQUEST_ALREADY_SENT", True)
    return current_action, current_reason, current_review_required


# Human-reviewed provider replies: conditional review hints, never authority.
# The exact original-message/thread relationship prevents stale advice from
# triggering another unnecessary buyer follow-up.
REVIEWED_BUYER_RESPONSES = {
    ("lead-smart", "1a0d9ce883c87d4a", "1a145b32d742f3b1"):
        ("BUYER_REPORTS_RECORDING_TEST_COMPLETE",
         "PREPARE_EXISTING_SUPERVISED_ROOFING_PILOT_NO_DUPLICATE_TEST"),
    ("inquirly.com", "1a0d9ef44c7f77d0", "1a14540463907582"):
        ("PARTNER_REPORTS_NO_PILOT_WITHOUT_ESTABLISHED_TRAFFIC",
         "DEFER_INQUIRLY_UNTIL_VERIFIED_TRAFFIC_NO_REPEAT_REQUEST"),
}


def reviewed_buyer_reply_disposition(
    key: str, *, thread_ids: set[str],
    last_inbound_message_id: str | None,
    last_inbound_at: datetime | None,
    last_outbound_at: datetime | None,
    source_fresh: bool, stage: str,
) -> dict[str, Any] | None:
    """Observed buyer-reply position, not consent, route or payable acceptance."""
    if (not source_fresh or stage != "INBOUND_REVIEW_REQUIRED"
            or len(thread_ids) != 1 or last_inbound_at is None
            or (last_outbound_at is not None
                and last_inbound_at <= last_outbound_at)):
        return None
    match = REVIEWED_BUYER_RESPONSES.get(
        (key, next(iter(thread_ids)), last_inbound_message_id)
    )
    if match is None:
        return None
    return {
        "status": match[0], "next_action": match[1],
        "source": "REVIEWED_PROVIDER_GMAIL_MESSAGE_CLAIM_ONLY",
        "canonical_buyer_identity_verified": False,
        "buyer_route_and_leg_independently_verified": False,
        "payable_event_verified": False,
        "outbound_authorized": False,
        "live_traffic_authorized": False,
        "execution_authority": "NONE",
    }


FOUNDER_FOLLOWUP_REVIEW_SECONDS = 7 * 24 * 3600


def founder_review_action(
    *, stage: str, hints: set[str], last_outbound: datetime | None,
    now: datetime, gmail_snapshot_fresh: bool,
    linked_gmail: bool,
) -> tuple[str, bool, str]:
    """Triage already-known relationships without proposing automatic sends.

    The 7-day threshold is only a reminder to *review*, never a trigger to
    contact someone, and cannot be trusted when the email snapshot is stale.
    """
    if linked_gmail and not gmail_snapshot_fresh:
        return 'REFRESH_MAILBOX_EVIDENCE', True, 'SOURCE_STALE'
    if stage == 'EVIDENCE_HOLD':
        return 'REVIEW_EVIDENCE_HOLD_NO_CONTACT', True, 'EVIDENCE_BLOCKED'
    if stage == 'DELIVERY_HOLD':
        return 'VERIFY_DELIVERY_CHANNEL_NO_RETRY', True, 'DELIVERY_BLOCKED'
    if stage == 'INBOUND_REVIEW_REQUIRED':
        if 'LANDING_APPROVAL_AND_ROUTE_PROOF' in hints:
            return 'REVIEW_BUYER_LANDING_APPROVAL_AND_ROUTE', True, 'BUYER_RESPONSE'
        return 'REVIEW_NEW_INBOUND_NO_AUTOSEND', True, 'BUYER_RESPONSE'
    overdue = bool(last_outbound is not None and
                   (now-last_outbound).total_seconds() >= FOUNDER_FOLLOWUP_REVIEW_SECONDS)
    if stage == 'AWAITING_BUYER':
        if overdue:
            return 'REVIEW_PENDING_BUYER_REQUEST', True, 'FOLLOWUP_REVIEW_DUE'
        if 'ONBOARDING_BUYBOX' in hints:
            return 'WAIT_BUYER_ONBOARDING_AND_MARKETS', False, 'WAITING_PARTNER'
        if 'WAITING_MARKET_DETAILS' in hints or 'REQUEST_BUYER_MARKETS' in hints:
            return 'WAIT_BUYER_MARKET_REQUIREMENTS', False, 'WAITING_PARTNER'
        return 'WAIT_BUYER_RESPONSE', False, 'WAITING_PARTNER'
    if stage == 'CONTACTED_AWAITING_RESPONSE':
        return ('REVIEW_FOLLOWUP_ELIGIBILITY' if overdue else 'WAIT_BUYER_RESPONSE',
                overdue, 'FOLLOWUP_REVIEW_DUE' if overdue else 'WAITING_PARTNER')
    if stage == 'RESEARCH_ONLY':
        return 'CONTINUE_AUTOMATED_FIRST_PARTY_QUALIFICATION', False, 'RESEARCH'
    raise RelationshipEvidenceError('unexpected_relationship_stage')


def when(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RelationshipEvidenceError("invalid_message_time")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RelationshipEvidenceError("invalid_message_time") from exc
    if timestamp.tzinfo is None:
        raise RelationshipEvidenceError("naive_message_time")
    return timestamp.astimezone(timezone.utc)


def ensure_source(src: Mapping[str, Any], *, now: datetime) -> bool:
    if src.get("schema_version") != SCHEMA:
        raise RelationshipEvidenceError("wrong_gmail_summary_schema")
    if src.get("origin") != "connected_gmail_connector_read_only":
        raise RelationshipEvidenceError("unsupported_gmail_summary_origin")
    if src.get("mailbox") != "flavag83@gmail.com":
        raise RelationshipEvidenceError("unexpected_gmail_mailbox")
    captured = when(src.get("captured_at"))
    if captured is None:
        raise RelationshipEvidenceError("missing_gmail_capture")
    age = (now - captured).total_seconds()
    if age < -300:
        raise RelationshipEvidenceError("future_gmail_capture")
    rows = src.get("threads")
    if not isinstance(rows, list) or len(rows) > 500:
        raise RelationshipEvidenceError("invalid_gmail_thread_count")
    return age <= MAX_AGE_SECONDS


def _str(value: Any, max_length: int = 200) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise RelationshipEvidenceError("invalid_string_value")
    return value.strip()


def _thread_row(row: Any, *, now: datetime) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RelationshipEvidenceError("invalid_thread")
    key = _str(row.get("entity_key"), 96).lower()
    if not VALID_KEY.fullmatch(key):
        raise RelationshipEvidenceError("invalid_entity_key")
    tid = _str(row.get("gmail_thread_id"), 35).lower()
    if not HEX_ID.fullmatch(tid):
        raise RelationshipEvidenceError("invalid_gmail_thread_id")
    domains = row.get("identity_domains")
    if not isinstance(domains, list) or not 1 <= len(domains) <= 8:
        raise RelationshipEvidenceError("invalid_identity_domains")
    identities = []
    for item in domains:
        domain = _str(item, 125).lower()
        if not VALID_DOMAIN.fullmatch(domain) or domain in ("gmail.com", "google.com"):
            raise RelationshipEvidenceError("invalid_identity_domain")
        identities.append(domain)
    inbound = when(row.get("last_inbound_at"))
    outbound = when(row.get("last_outbound_at"))
    for timestamp in (inbound, outbound):
        if timestamp and (timestamp - now).total_seconds() > 300:
            raise RelationshipEvidenceError("future_email_message")
    inbound_id = row.get("last_inbound_message_id")
    outbound_id = row.get("last_outbound_message_id")
    for value in (inbound_id, outbound_id):
        if value is not None and not HEX_ID.fullmatch(_str(value, 35).lower()):
            raise RelationshipEvidenceError("invalid_message_id")
    if (inbound is None) != (inbound_id is None):
        raise RelationshipEvidenceError("inbound_timestamp_id_mismatch")
    if (outbound is None) != (outbound_id is None):
        raise RelationshipEvidenceError("outbound_timestamp_id_mismatch")
    bounces = row.get("bounced_addresses", [])
    if not isinstance(bounces, list) or len(bounces) > 12:
        raise RelationshipEvidenceError("invalid_bounce_list")
    bounce_addresses = []
    for value in bounces:
        address = _str(value, 254).lower()
        if not re.fullmatch(r"[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,24}", address):
            raise RelationshipEvidenceError("invalid_bounce_address")
        bounce_addresses.append(address)
    hint = row.get("next_action_code", "REVIEW_ONLY")
    if hint not in ALLOWED_HINTS:
        raise RelationshipEvidenceError("unapproved_next_action_code")
    events = row.get("buyer_signal_events", [])
    if not isinstance(events,list) or len(events)>120:
        raise RelationshipEvidenceError("invalid_buyer_recognition_count")
    safe_events = []
    seen_events = set()
    for event in events:
        if not isinstance(event,dict) or set(event)!={
            "message_id","event_code","observed_at","evidence_grade","direction",
        }:
            raise RelationshipEvidenceError("invalid_buyer_recognition_record")
        mid = event["message_id"]
        code = event["event_code"]
        moment = when(event["observed_at"])
        direction = event["direction"]
        if (not isinstance(mid,str) or not HEX_ID.fullmatch(mid)
                or code not in EVENT_CODES or moment is None
                or (moment-now).total_seconds()>300
                or event["evidence_grade"]!="EMAIL_REPORTED_UNVERIFIED"
                or direction not in ("inbound","outbound")
                or (code in ("PILOT_TECHNICAL_REQUIREMENTS_SENT",
                             "COMPLETE_BUYER_REQUIREMENTS_SENT"))!=(direction=="outbound")
                or (mid,code) in seen_events):
            raise RelationshipEvidenceError("untrusted_buyer_recognition")
        seen_events.add((mid,code))
        safe_events.append(dict(event))
    return {
        "entity_key": key, "company": _str(row.get("company"), 150),
        "identity_domains": sorted(set(identities)),
        "gmail_thread_id": tid,
        "last_inbound_at": inbound,
        "last_outbound_at": outbound,
        "last_inbound_message_id": inbound_id,
        "last_outbound_message_id": outbound_id,
        "bounced_addresses": sorted(set(bounce_addresses)),
        "next_action_code": hint,
        "buyer_signal_events": safe_events,
    }


def reconcile(
    source: Mapping[str, Any],
    queue: Mapping[str, Any],
    qualification: Mapping[str, Any],
    *,
    now: datetime | None = None,
    previous: Mapping[str, Any] | None = None,
    do_not_pursue_domains: frozenset[str] | None = None,
) -> dict[str, Any]:
    # Founder policy is authoritative even when the agent consumes stale Gmail
    # or buyer-queue snapshots. It never creates outbound authority.
    exclusions = (founder_do_not_pursue_domains()
                  if do_not_pursue_domains is None
                  else frozenset(do_not_pursue_domains))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise RelationshipEvidenceError("naive_now")
    now = now.astimezone(timezone.utc)
    fresh = ensure_source(source, now=now)
    # A connector may refresh only explicitly checked buyer threads. Do NOT
    # mark all 57 other historical messages fresh from a four-thread scan.
    partial_at = when(source.get("partial_update_at"))
    partial_ids = source.get("partial_updated_thread_ids", [])
    if not isinstance(partial_ids, list) or len(partial_ids) > 500:
        raise RelationshipEvidenceError("invalid_partial_gmail_thread_set")
    if any(not isinstance(tid, str) or not HEX_ID.fullmatch(tid)
           for tid in partial_ids) or len(set(partial_ids)) != len(partial_ids):
        raise RelationshipEvidenceError("invalid_partial_gmail_thread_ids")
    if partial_at is None and partial_ids:
        raise RelationshipEvidenceError("missing_partial_gmail_capture_time")
    if partial_at is not None and (partial_at - now).total_seconds() > 300:
        raise RelationshipEvidenceError("future_partial_gmail_capture")
    partial_fresh = (
        partial_at is not None
        and 0 <= (now-partial_at).total_seconds() <= MAX_AGE_SECONDS
    )
    refreshed_threads = set(partial_ids) if partial_fresh else set()
    candidates = queue.get("candidates")
    targets = qualification.get("targets")
    if not isinstance(candidates, list) or not isinstance(targets, list):
        raise RelationshipEvidenceError("missing_canonical_buyer_queue")
    if queue.get("candidate_count") != len(candidates) or qualification.get("shortlisted_count") != len(targets):
        raise RelationshipEvidenceError("canonical_queue_count_mismatch")

    registry: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for raw in source["threads"]:
        item = _thread_row(raw, now=now)
        key = item["entity_key"]
        for domain in item["identity_domains"]:
            if domain in aliases and aliases[domain] != key:
                raise RelationshipEvidenceError("ambiguous_company_alias")
            aliases[domain] = key
        target = registry.setdefault(key, {
            "entity_key": key, "company": item["company"],
            "identity_domains": set(),
            "gmail_thread_ids": set(), "bounced_addresses": set(),
            "last_inbound_at": None, "last_outbound_at": None,
            "last_inbound_message_id": None, "last_outbound_message_id": None,
            "next_action_codes": set(), "discovery_status": None,
            "qualification_tier": None,
            "founder_priority": 0,
            "buyer_signal_events": [],
        })
        target["buyer_signal_events"].extend(item["buyer_signal_events"])
        if len(target["buyer_signal_events"])>300:
            raise RelationshipEvidenceError("too_many_buyer_recognition_events")
        target["identity_domains"].update(item["identity_domains"])
        target["gmail_thread_ids"].add(item["gmail_thread_id"])
        target["bounced_addresses"].update(item["bounced_addresses"])
        target["next_action_codes"].add(item["next_action_code"])
        for direction in ("inbound", "outbound"):
            ts = item[f"last_{direction}_at"]
            if ts and (target[f"last_{direction}_at"] is None or ts > target[f"last_{direction}_at"]):
                target[f"last_{direction}_at"] = ts
                target[f"last_{direction}_message_id"] = item[f"last_{direction}_message_id"]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if not VALID_DOMAIN.fullmatch(domain):
            continue
        key = aliases.get(domain, domain)
        record = registry.setdefault(key, {
            "entity_key": key, "company": domain,
            "identity_domains": set(), "gmail_thread_ids": set(),
            "bounced_addresses": set(), "next_action_codes": set(),
            "last_inbound_at": None, "last_outbound_at": None,
            "last_inbound_message_id": None, "last_outbound_message_id": None,
            "discovery_status": None, "qualification_tier": None,
            "founder_priority": 0,
        })
        record["identity_domains"].add(domain)
        record["discovery_status"] = item.get("status", "WATCH")
    for item in targets:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if not VALID_DOMAIN.fullmatch(domain):
            continue
        key = aliases.get(domain, domain)
        record = registry.get(key)
        if not record:
            continue
        record["qualification_tier"] = item.get("tier")
        score = item.get("founder_priority")
        if type(score) is int and 0 <= score <= 100:
            record["founder_priority"] = max(score, record["founder_priority"])

    old = {r.get("entity_key"): r for r in (previous or {}).get("relationships", [])
           if isinstance(r, dict)}
    result = []
    newly_received = 0
    for key, record in registry.items():
        inc = record["last_inbound_at"]
        out = record["last_outbound_at"]
        founder_excluded = any(domain in exclusions for domain in record["identity_domains"])
        if founder_excluded:
            stage = "EVIDENCE_HOLD"
        elif record["qualification_tier"] in ("MANUAL_EVIDENCE_HOLD", "AUTOMATED_EVIDENCE_HOLD"):
            stage = "EVIDENCE_HOLD"
        elif record["bounced_addresses"] and not inc:
            stage = "DELIVERY_HOLD"
        elif inc and (out is None or inc > out):
            stage = "INBOUND_REVIEW_REQUIRED"
        elif inc and out and out >= inc:
            stage = "AWAITING_BUYER"
        elif out:
            stage = "CONTACTED_AWAITING_RESPONSE"
        else:
            stage = "RESEARCH_ONLY"
        record_mail_fresh = fresh or bool(
            record["gmail_thread_ids"] & refreshed_threads
        )
        new_reply = (
            record_mail_fresh and inc is not None
            and key in old and record["last_inbound_message_id"] != old[key].get("last_inbound_message_id")
        )
        newly_received += bool(new_reply)
        founder_action, needs_review, action_reason = founder_review_action(
            stage=stage, hints=record['next_action_codes'], last_outbound=out,
            now=now, gmail_snapshot_fresh=record_mail_fresh,
            linked_gmail=bool(record['gmail_thread_ids']),
        )
        reviewed_request = reviewed_request_duplicate_guard(
            key, {
                "gmail_thread_ids": record["gmail_thread_ids"],
                "last_outbound_message_id": record["last_outbound_message_id"],
                "gmail_snapshot_fresh": record_mail_fresh,
                "buyer_signal_events": record.get("buyer_signal_events", []),
            }
        )
        founder_action, action_reason, needs_review = _apply_reviewed_request_to_action(
            key, reviewed_request, current_action=founder_action,
            current_reason=action_reason, current_review_required=needs_review,
        )
        # The original Gmail message is already present in our existing
        # read-only metadata index. Never promote the email claim to actual
        # buyer acceptance or supersede a hold / contact suppression.
        disposition = reviewed_buyer_reply_disposition(
            key, thread_ids=record["gmail_thread_ids"],
            last_inbound_message_id=record["last_inbound_message_id"],
            last_inbound_at=inc, last_outbound_at=out,
            source_fresh=record_mail_fresh, stage=stage,
        )
        if disposition is not None and not founder_excluded:
            founder_action = disposition["next_action"]
            action_reason = disposition["status"]
            needs_review = key == "lead-smart"
        if founder_excluded:
            founder_action = "DO_NOT_PURSUE_NO_CONTACT"
            needs_review = False
            action_reason = "FOUNDER_DO_NOT_PURSUE_HARD_BOUNCE_CREDIBILITY"
        result.append({
            "entity_key": key, "company": record["company"],
            "identity_domains": sorted(record["identity_domains"]),
            "gmail_thread_ids": sorted(record["gmail_thread_ids"]),
            "gmail_url": (
                "https://mail.google.com/mail/u/0/#all/"
                + sorted(record["gmail_thread_ids"])[0]
                if record["gmail_thread_ids"] else None
            ),
            "last_inbound_at": inc.isoformat() if inc else None,
            "last_outbound_at": out.isoformat() if out else None,
            "last_inbound_message_id": record["last_inbound_message_id"],
            "last_outbound_message_id": record["last_outbound_message_id"],
            "bounced_addresses": sorted(record["bounced_addresses"]),
            "stage": stage,
            "next_action_codes": sorted(record["next_action_codes"]),
            "next_founder_action": founder_action,
            "founder_review_required": needs_review,
            "founder_action_reason": action_reason,
            "auto_send_authorized": False,
            "do_not_pursue": founder_excluded,
            "new_inbound_since_last_snapshot": bool(new_reply),
            "discovery_status": record["discovery_status"],
            "qualification_tier": record["qualification_tier"],
            "founder_priority": record["founder_priority"],
            "gmail_snapshot_fresh": record_mail_fresh,
            # Deterministic recognition reports what a buyer *said*, not
            # verified legal consent, actual routing, pricing or call success.
            "automatically_recognized_buyer_events": sorted(
                record.get("buyer_signal_events", []),
                key=lambda x: (x["observed_at"], x["message_id"], x["event_code"]),
            ),
            "recognized_buyer_events_are_verified": False,
            "buyer_onboarding_duplicate_guard": reviewed_request,
            "reviewed_buyer_reply_disposition": disposition,
            "commercial_buyer_approved": False,
            "suppression_evidence_complete": False,
            "outbound_authorized": False,
            "realised_revenue_proven": False,
        })
    rank = {"INBOUND_REVIEW_REQUIRED": 0, "AWAITING_BUYER": 1,
            "EVIDENCE_HOLD": 2, "DELIVERY_HOLD": 3,
            "CONTACTED_AWAITING_RESPONSE": 4, "RESEARCH_ONLY": 5}
    result.sort(key=lambda r: (rank[r["stage"]], -r["founder_priority"], r["company"]))
    unlinked = source.get("buyer_new_thread_review", [])
    if not isinstance(unlinked,list) or len(unlinked)>48:
        raise RelationshipEvidenceError("invalid_unlinked_buyer_thread_review")
    safe_review=[]
    seen_unlinked=set()
    for row in unlinked:
        if (not isinstance(row,Mapping)
                or not {"thread_id","domain","last_buyer_reply_id",
                              "status","source","outbound_authorized","execution_authority"} <= set(row)
                or set(row)-{"thread_id","domain","last_buyer_reply_id",
                              "status","source","outbound_authorized","execution_authority",
                              "reported_constraint"}):
            raise RelationshipEvidenceError("untrusted_unlinked_buyer_review_row")
        tid=row["thread_id"]
        domain=row["domain"]
        mid=row["last_buyer_reply_id"]
        if (not isinstance(tid,str) or not HEX_ID.fullmatch(tid)
                or tid in seen_unlinked or not isinstance(mid,str) or not HEX_ID.fullmatch(mid)
                or not isinstance(domain,str) or not VALID_DOMAIN.fullmatch(domain)
                or domain in ("gmail.com","yahoo.com","outlook.com","hotmail.com")
                or row["status"] not in (
                    "REVIEW_IDENTITY_NO_SEND","REVIEW_MONITORING_CAP_NO_SEND",
                    "HOLD_PAID_PLACEMENTS_ONLY_NO_PERFORMANCE_CONTACT",
                )
                or row.get("reported_constraint") not in (
                    None,"SPONSORED_PLACEMENTS_ONLY_REPORTED"
                )
                or (row["status"]=="HOLD_PAID_PLACEMENTS_ONLY_NO_PERFORMANCE_CONTACT") != (
                    row.get("reported_constraint")=="SPONSORED_PLACEMENTS_ONLY_REPORTED"
                )
                or row["source"]!="EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED"
                or row["outbound_authorized"] is not False
                or row["execution_authority"]!="NONE"):
            raise RelationshipEvidenceError("invalid_unlinked_buyer_review_identity")
        seen_unlinked.add(tid)
        safe_review.append(dict(row))
    raw = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    counts = {stage: sum(r["stage"] == stage for r in result) for stage in rank}
    # Warm two-way correspondence is a separate, compact founder signal.
    # Do not bury live partnerships beneath dozens of bounced/cold records.
    warm = [
        {
            "entity_key": item['entity_key'], "company": item['company'],
            "stage": item['stage'], "next_founder_action": item['next_founder_action'],
            "buyer_onboarding_duplicate_guard": item["buyer_onboarding_duplicate_guard"],
            "reviewed_buyer_reply_disposition": item["reviewed_buyer_reply_disposition"],
            "automatically_recognized_buyer_events": item["automatically_recognized_buyer_events"],
            "gmail_url": item['gmail_url'],
            "last_inbound_at": item['last_inbound_at'],
            "last_outbound_at": item['last_outbound_at'],
            "founder_priority": item['founder_priority'],
            "gmail_snapshot_fresh": item['gmail_snapshot_fresh'],
            "partner_commercial_terms_verified": False,
            "outbound_authorized": False,
        }
        for item in result
        if item['last_inbound_at'] is not None
        and item['gmail_thread_ids']
        and item['stage'] in ('INBOUND_REVIEW_REQUIRED','AWAITING_BUYER')
    ]
    review_queue = [
        {
            "entity_key": item["entity_key"], "company": item["company"],
            "stage": item["stage"], "next_founder_action": item["next_founder_action"],
            "buyer_onboarding_duplicate_guard": item["buyer_onboarding_duplicate_guard"],
            "reviewed_buyer_reply_disposition": item["reviewed_buyer_reply_disposition"],
            "automatically_recognized_buyer_events": item["automatically_recognized_buyer_events"],
            "reason": item["founder_action_reason"],
            "last_inbound_at": item["last_inbound_at"],
            "last_outbound_at": item["last_outbound_at"],
            "gmail_url": item["gmail_url"],
            "founder_priority": item["founder_priority"],
            "outbound_authorized": False,
        }
        for item in result if item["founder_review_required"]
    ]
    return {
        "schema_version": OUTPUT_SCHEMA,
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "source_mailbox": source["mailbox"],
        "gmail_snapshot_captured_at": source["captured_at"],
        "gmail_snapshot_fresh": fresh,
        "partial_gmail_thread_scan_at": (
            partial_at.isoformat() if partial_at is not None else None
        ),
        "partial_gmail_thread_count_fresh": len(refreshed_threads),
        "automatic_live_gmail_ingest_configured": False,
        "gmail_source_sha256": sha256(raw).hexdigest(),
        "discovery_queue_generated_at": queue.get("generated_at"),
        "relationship_count": len(result),
        "new_engaged_buyer_identity_review_count":len(safe_review),
        "new_engaged_buyer_identity_review_queue":safe_review,
        "new_engaged_buyer_review_outbound_authorized":False,
        "founder_do_not_pursue_count": sum(bool(r["do_not_pursue"]) for r in result),
        "linked_gmail_thread_count": sum(len(r["gmail_thread_ids"]) for r in result),
        "stage_counts": counts,
        "founder_review_required_count": len(review_queue),
        "warm_business_relationship_count": len(warm),
        "warm_business_action_queue": warm[:8],
        "partner_pilot_readiness_queue": partner_pilot_readiness(result),
        "partner_pilot_readiness_is_activation_authority": False,
        "warm_business_queue_truncated": len(warm)>8,
        "founder_action_queue": review_queue,
        "founder_action_queue_truncated": False,
        "founder_actions_are_draft_only": True,
        "next_actions_automatic_sends": False,
        "new_inbound_relationships_since_prior_snapshot": newly_received,
        "outbound_sent": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
        "relationships": result,
    }


# Operational evidence review of company-published recruitment notices.
# A social post is not a buy-box, company authority proof or outreach approval.
def classify_publisher_demand_post(excerpt: str) -> str:
    text = excerpt.lower()
    buyer = bool(re.search(
        r"\b(?:actively buying|currently buying|we(?:'re| are) buying|"
        r"looking for (?:quality |reliable |inbound call )?publishers|"
        r"onboarding (?:inbound call )?publishers|"
        r"buying (?:home services |quality )?calls)\b", text,
    ))
    if re.search(r"\b(?:not|no longer|stopped)\s+(?:actively\s+)?buying\b", text):
        buyer = False
    supplier = bool(re.search(
        r"\b(?:looking for (?:new |direct )?(?:call )?buyers|"
        r"looking to (?:sell|find buyers)|"
        r"(?:we(?:'re| are) )?(?:selling|offering) (?:inbound |quality )?calls|"
        r"calls available|calls for sale)\b", text,
    ))
    if buyer and supplier:
        return "MIXED_BUY_AND_SELL_CLAIMS"
    if buyer:
        return "PUBLIC_PUBLISHER_RECRUITMENT_CLAIM"
    if supplier:
        return "PUBLIC_CALL_SUPPLY_PITCH"
    return "UNCLASSIFIED_NETWORK_PROMOTION"


def attach_known_company_public_demand(report: dict[str, Any], reviewed: Mapping[str, Any]) -> dict[str, Any]:
    """Attach manually reviewed public demand to KNOWN companies, never CRM promotion."""
    from urllib.parse import urlparse
    if (not isinstance(reviewed, Mapping)
            or reviewed.get("schema_version") != "empire.public_network_demand_review.v1"
            or reviewed.get("origin") != "human_reviewed_public_business_sources"):
        raise RelationshipEvidenceError("untrusted_public_demand_source")
    items = reviewed.get("observations")
    if not isinstance(items, list) or len(items) > 12:
        raise RelationshipEvidenceError("invalid_public_demand_count")
    companies = {d: r for r in report["relationships"]
                 for d in r.get("identity_domains", [])}
    results = []
    seen = set()
    for item in items:
        if not isinstance(item, Mapping) or set(item) != {
            "entity_key", "source_url", "observed_date", "post_excerpt",
            "attribution_type", "caution_codes", "official_site_evidence_url",
        }:
            raise RelationshipEvidenceError("invalid_public_demand_shape")
        domain = item["entity_key"]
        url = item["source_url"]
        excerpt = item["post_excerpt"]
        day = item["observed_date"]
        site = item["official_site_evidence_url"]
        if (not isinstance(domain, str) or domain not in companies
                or companies[domain]["entity_key"] in seen):
            raise RelationshipEvidenceError("unknown_or_duplicate_known_company")
        rec = companies[domain]
        seen.add(rec["entity_key"])
        if (not isinstance(url, str) or len(url) > 700
                or not isinstance(excerpt, str) or len(excerpt) > 650
                or len(excerpt.strip()) < 28
                or any(ord(c) < 32 for c in excerpt)):
            raise RelationshipEvidenceError("unsafe_public_demand_evidence")
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
        except (TypeError, ValueError):
            raise RelationshipEvidenceError("bad_public_source_url")
        if (parsed.scheme != "https" or host not in
                ("www.linkedin.com", "linkedin.com", domain, "www." + domain)):
            raise RelationshipEvidenceError("wrong_public_source_host")
        site_host = urlparse(site).hostname if isinstance(site, str) else None
        if (not isinstance(site, str) or len(site) > 700
                or urlparse(site).scheme != "https"
                or site_host not in (domain, "www." + domain)):
            raise RelationshipEvidenceError("site_corroboration_host_mismatch")
        if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise RelationshipEvidenceError("invalid_public_review_date")
        try:
            checked = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError as exc:
            raise RelationshipEvidenceError("invalid_public_review_date") from exc
        generated = when(report.get("generated_at"))
        if generated is None or checked > generated.date():
            raise RelationshipEvidenceError("public_review_from_future")
        if item["attribution_type"] not in (
            "COMPANY_PAGE", "NAMED_PERSON_SELF_IDENTIFIED",
        ):
            raise RelationshipEvidenceError("unreviewed_company_attribution")
        cautions = item["caution_codes"]
        allowed = {"EXAMPLE_PHONE_NUMBER_ON_WEBSITE",
                   "BIDIRECTIONAL_BUYER_AND_SELLER_NETWORK",
                   "POSSIBLE_TEMPLATE_CONTACT_DETAILS_ON_WEBSITE",
                   "POST_PUBLICATION_DATE_NOT_INDEPENDENTLY_VERIFIED"}
        if (not isinstance(cautions, list) or len(cautions) > 3
                or any(x not in allowed for x in cautions)
                or len(set(cautions)) != len(cautions)):
            raise RelationshipEvidenceError("untrusted_public_caution_codes")
        kind = classify_publisher_demand_post(excerpt)
        entry = {
            "entity_key": rec["entity_key"],
            "domain": domain,
            "company": rec["company"],
            "previous_contact_stage": rec["stage"],
            "previous_outreach_observed": bool(rec.get("last_outbound_at")),
            "source_url": url,
            "official_site_evidence_url": site,
            "observed_date": day,
            "post_publication_date_verified": False,
            "excerpt_sha256": sha256(excerpt.encode("utf-8")).hexdigest(),
            "post_role_class": kind,
            "source_attribution_type": item["attribution_type"],
            "caution_codes": cautions,
            "buyer_campaign_active_confirmed": False,
            "current_geography_and_price_verified": False,
            "sender_or_speaker_contact_verified": False,
            "recontact_requires_suppression_and_founder_review": True,
            "outbound_authorized": False,
            "execution_authority": "NONE",
        }
        results.append(entry)
        rec["public_buying_pulse_review"] = entry
    results.sort(key=lambda x: (
        0 if x["post_role_class"] == "PUBLIC_PUBLISHER_RECRUITMENT_CLAIM" else 1,
        x["entity_key"],
    ))
    report["known_company_public_demand_review"] = {
        "schema_version": "empire.known_company_public_demand_review.v1",
        "mode": "OBSERVE",
        "reviewed_known_companies": len(results),
        "explicit_publisher_recruitment_claims": sum(
            x["post_role_class"] == "PUBLIC_PUBLISHER_RECRUITMENT_CLAIM"
            for x in results
        ),
        "verified_new_buyers": 0,
        "verified_call_capacity": 0,
        "outbound_sent": False,
        "execution_authority": "NONE",
        "rows": results,
    }
    return report
