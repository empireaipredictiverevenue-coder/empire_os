"""Existing receptionist -> RecoveryLedger read-only integration regression."""
from dataclasses import replace

import pytest

from empire_os.inbound_reception_intake import draft_for_call
from empire_os.inbound_reception_recovery_bridge import project_reception_recovery_review
from empire_os.inbound_revenue_recovery import RecoveryEvent


def draft(tenant="tenant-a", call="call-12345678", kind="appointment"):
    return draft_for_call(
        tenant_id=tenant, call_id=call, kind=kind,
        service="roofing", window="morning",
    )


def provider(kind, *, tenant="tenant-a", call="call-12345678", stamp="09:00",
             synthetic=False, verified=True):
    return RecoveryEvent(
        tenant_id=tenant, call_id=call, event_id=call + "-" + kind,
        occurred_at="2026-10-21T" + stamp + ":00+00:00",
        kind=kind, origin="provider", synthetic=synthetic, verified=verified,
        evidence_ref="synthetic-test-provider-receipt",
    )


def test_synthetic_appointment_review_never_claims_lead_or_recovered_revenue():
    result = project_reception_recovery_review("tenant-a", [draft()])
    assert result["enquiry_drafts_count"] == 1
    item, = result["review_items"]
    assert item["status"] == "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
    assert item["provider_observation"] == "NO_AUTHENTICATED_PROVIDER_DISPOSITION"
    assert item["authorized_to_contact"] is False
    assert item["caller_contact_identity_verified"] is False
    assert item["appointment_confirmed"] is False
    assert result["new_crm_prospects"] == 0
    assert result["crm_writes"] is False
    assert result["recovery_scorecard"]["verified_recovered_calls"] == 0
    assert result["recovery_scorecard"]["verified_paid_recovery_minor_by_currency"] == {}


def test_existing_trusted_answer_is_not_marked_missed_or_recovered():
    result = project_reception_recovery_review(
        "tenant-a", [draft()], [provider("answered")],
        provider_source_authenticated=True,
    )
    item, = result["review_items"]
    assert item["provider_observation"] == "PROVIDER_ANSWERED_NOT_MISSED"
    assert result["recovery_scorecard"]["answered_calls"] == 1
    assert result["recovery_scorecard"]["missed_calls"] == 0
    assert result["recovery_scorecard"]["verified_recovered_calls"] == 0


def test_missing_independent_authentication_cannot_change_draft_status():
    result = project_reception_recovery_review(
        "tenant-a", [draft()], [provider("unanswered")],
        provider_source_authenticated=False,
    )
    assert result["review_items"][0]["provider_observation"] == (
        "NO_AUTHENTICATED_PROVIDER_DISPOSITION"
    )
    assert result["review_items"][0]["authorized_to_contact"] is False


def test_unresolved_missed_is_not_a_qualified_paid_recovery():
    result = project_reception_recovery_review(
        "tenant-a", [draft()], [provider("unanswered")],
        provider_source_authenticated=True,
    )
    assert result["review_items"][0]["provider_observation"] == "PROVIDER_MISSED_UNRESOLVED"
    assert result["recovery_scorecard"]["missed_calls"] == 1
    assert result["recovery_scorecard"]["verified_recovered_calls"] == 0
    assert result["recovered_revenue_claimed"] is False


def test_conflicting_provider_disposition_requires_review():
    result = project_reception_recovery_review(
        "tenant-a", [draft()],
        [provider("unanswered"), provider("answered")],
        provider_source_authenticated=True,
    )
    assert result["review_items"][0]["provider_observation"] == (
        "CONFLICTING_ANSWER_AND_MISSED_EVENTS_REVIEW"
    )


def test_duplicate_same_draft_is_one_review_item():
    one = draft()
    result = project_reception_recovery_review("tenant-a", [one, one])
    assert result["enquiry_drafts_count"] == 1


def test_different_draft_for_same_enquiry_or_call_is_rejected():
    one = draft()
    with pytest.raises(ValueError, match="conflicting_reception_draft_id"):
        project_reception_recovery_review(
            "tenant-a", [one, replace(one, requested_service="solar")]
        )
    with pytest.raises(ValueError, match="duplicate_call_different_enquiry"):
        project_reception_recovery_review(
            "tenant-a", [one, replace(one, enquiry_id="different")]
        )


@pytest.mark.parametrize("change", [
    {"caller_consented_to_review": False},
    {"crm_write_performed": True},
    {"outbound_authorized": True},
    {"appointment_confirmed": True},
    {"contact_identity_included": True},
    {"status": "ACCEPTED"},
    {"source": "external_untrusted"},
])
def test_unsafe_draft_cannot_be_promoted_to_review(change):
    with pytest.raises(ValueError, match="reception_draft_not_eligible"):
        project_reception_recovery_review("tenant-a", [replace(draft(), **change)])


def test_tenant_filter_blocks_leaking_other_businesses():
    results = project_reception_recovery_review(
        "tenant-a",
        [draft("tenant-a"), draft("tenant-b", call="foreign-12345")],
        [provider("unanswered", tenant="tenant-b")],
        provider_source_authenticated=True,
    )
    assert results["enquiry_drafts_count"] == 1
    assert results["review_items"][0]["tenant_id"] == "tenant-a"
    assert results["recovery_scorecard"]["calls_observed"] == 0


def test_untrusted_synthetic_provider_event_never_qualifies_status():
    results = project_reception_recovery_review(
        "tenant-a", [draft()], [provider("unanswered", synthetic=True)],
        provider_source_authenticated=True,
    )
    assert results["review_items"][0]["provider_observation"] == (
        "NO_AUTHENTICATED_PROVIDER_DISPOSITION"
    )
    assert results["recovery_scorecard"]["missed_calls"] == 0


def test_provider_boolean_must_be_boolean():
    with pytest.raises(ValueError, match="provider_source_flag_must_be_boolean"):
        project_reception_recovery_review(
            "tenant-a", [draft()], provider_source_authenticated=1
        )
