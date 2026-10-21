"""Read-only bridge between existing receptionist drafts and Revenue Recovery.

Does not create CRM prospects, new recovery stores, DB tables, SMS, callbacks
or calendar bookings. Uses the original RecoveryLedger and scorecard. Input
events are trusted only if an independent caller actually authenticated them;
a bool in a test does not constitute production proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from empire_os.inbound_reception_intake import CRMEnquiryDraft
from empire_os.inbound_recovery_scorecard import build_inbound_recovery_scorecard
from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger, MISSED_STATUSES


@dataclass(frozen=True)
class ReceptionHandoffReview:
    tenant_id: str
    enquiry_id: str
    call_id: str
    enquiry_type: str
    service_code: str
    time_preference: str
    status: str
    provider_observation: str
    crm_acceptance: str = "NOT_SUBMITTED"
    caller_contact_identity_verified: bool = False
    authorized_to_contact: bool = False
    appointment_confirmed: bool = False
    recovered_call_claimed: bool = False
    money_claimed: bool = False


def project_reception_recovery_review(
    tenant_id: str,
    drafts: Iterable[CRMEnquiryDraft],
    provider_events: Iterable[RecoveryEvent] = (),
    *,
    provider_source_authenticated: bool = False,
) -> dict:
    """Project a tenant-specific private review. No mutation or outbound authority.

    For production, ONLY a trusted signed-and-replayed provider reader may
    pass provider_source_authenticated=True. A test caller's flag is not proof.
    Even with this flag, a CRM draft is never an accepted lead or recovered
    missed call.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("recovery_bridge_tenant_required")
    if type(provider_source_authenticated) is not bool:
        raise ValueError("provider_source_flag_must_be_boolean")
    by_call: dict[str, list[RecoveryEvent]] = {}
    ledger = RecoveryLedger()
    for event in provider_events:
        if not isinstance(event, RecoveryEvent):
            raise ValueError("invalid_recovery_bridge_event")
        if event.tenant_id != tenant_id:
            # No cross-tenant data can affect this projection.
            continue
        # Source authority here is Voice, not Calendar or Payments. Ignore
        # any unsupported actor's claim until its *own* canonical reader
        # proves the receipt. Do not count synthetic/unverified records.
        if (provider_source_authenticated and event.origin == "provider"
            and event.verified and not event.synthetic):
            ledger.append(event)
            if event.kind in MISSED_STATUSES | {"answered"}:
                by_call.setdefault(event.call_id, []).append(event)
    # Preserve canonical realised-revenue semantics but do not expose money
    # unless trusted provider receipt provenance is explicitly supplied.
    scorecard = build_inbound_recovery_scorecard(ledger.report(tenant_id))
    seen_enquiry: dict[str, CRMEnquiryDraft] = {}
    seen_call: dict[str, str] = {}
    review: list[ReceptionHandoffReview] = []
    for draft in drafts:
        if not isinstance(draft, CRMEnquiryDraft):
            raise ValueError("invalid_reception_draft")
        if draft.tenant_id != tenant_id:
            continue
        if (draft.status != "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
            or not draft.caller_consented_to_review
            or draft.crm_write_performed
            or draft.outbound_authorized
            or draft.appointment_confirmed
            or draft.contact_identity_included
            or draft.source != "signed_inbound_reception_candidate"):
            raise ValueError("reception_draft_not_eligible_for_review")
        if draft.enquiry_type not in {"appointment", "callback"}:
            raise ValueError("invalid_reception_draft_kind")
        if draft.enquiry_id in seen_enquiry:
            if seen_enquiry[draft.enquiry_id] != draft:
                raise ValueError("conflicting_reception_draft_id")
            continue
        if draft.call_id in seen_call and seen_call[draft.call_id] != draft.enquiry_id:
            raise ValueError("duplicate_call_different_enquiry")
        seen_enquiry[draft.enquiry_id] = draft
        seen_call[draft.call_id] = draft.enquiry_id
        statuses = {item.kind for item in by_call.get(draft.call_id, [])}
        if statuses & MISSED_STATUSES and "answered" in statuses:
            observation = "CONFLICTING_ANSWER_AND_MISSED_EVENTS_REVIEW"
        elif "answered" in statuses:
            observation = "PROVIDER_ANSWERED_NOT_MISSED"
        elif statuses & MISSED_STATUSES:
            observation = "PROVIDER_MISSED_UNRESOLVED"
        else:
            observation = "NO_AUTHENTICATED_PROVIDER_DISPOSITION"
        review.append(ReceptionHandoffReview(
            tenant_id=tenant_id,
            enquiry_id=draft.enquiry_id, call_id=draft.call_id,
            enquiry_type=draft.enquiry_type,
            service_code=draft.requested_service,
            time_preference=draft.preferred_time_window,
            status="PENDING_HUMAN_REVIEW_NOT_SUBMITTED",
            provider_observation=observation,
        ))
    # An existing scorecard may include prior real evidence; do not extrapolate
    # it from receptionist drafts. Provider provenance isn't established by the
    # ledger object itself; every score is qualified as independently unverified.
    return {
        "schema": "empire.inbound.reception_recovery_owner_review.v1",
        "tenant_id": tenant_id,
        "mode": "READ_ONLY_OFFLINE_PROJECTION",
        "source_authenticated_by_caller": provider_source_authenticated,
        "provider_authenticity_independently_verified_here": False,
        "enquiry_drafts_count": len(review),
        "review_items": [item.__dict__.copy() for item in sorted(
            review, key=lambda item: (item.call_id, item.enquiry_id))],
        "recovery_scorecard": {
            **scorecard,
            "evidence_level": "OFFLINE_OR_TRUSTED_READER_NOT_INDEPENDENT_PROOF",
            "claimable_as_realised_revenue_from_reception_drafts": False,
            # Surface no authenticated paid results from an untrusted caller
            # claiming provenance via a local function argument.
            "verified_paid_recovery_minor_by_currency": {},
        },
        "crm_writes": False,
        "new_crm_prospects": 0,
        "outbound_sent": False,
        "booking_confirmed_by_bridge": False,
        "recovered_revenue_claimed": False,
    }
