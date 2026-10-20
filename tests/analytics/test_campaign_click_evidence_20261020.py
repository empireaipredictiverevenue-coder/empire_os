"""Gateway-independent click evidence contract; fixtures are never live data."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.analytics.campaign_click_evidence import (
    CampaignLinkBinding, ClickEvidenceHeld, GatewayClickReceipt,
    issue_offline_link_token, review_offline_click_receipts,
    token_nonce_untrusted, verify_offline_link_token, MAX_BATCH,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
KEY = b"k" * 32
NONCE = "a" * 32
EVENT = "b" * 32
BINDING = CampaignLinkBinding(
    tenant_ref="tenant_empireai",
    campaign_id="campaign_" + "c" * 24,
    link_id="link_" + "d" * 24,
    recipient_lookup_key="e" * 32,
    destination_path="/predictive-revenue",
    channel="email",
    contact_permission="permitted",
)


def link(binding=BINDING, *, nonce=NONCE, start=NOW, end=None, key=KEY):
    return issue_offline_link_token(
        binding, secret=key, nonce=nonce, issued_at=start,
        expires_at=end or start + timedelta(days=2),
    )


def receipts(automation="suspected_human", binding=BINDING, verified=True):
    tok = link()
    receipt = GatewayClickReceipt(
        gateway_event_id=EVENT, link_token=tok,
        observed_at=NOW + timedelta(minutes=1),
        automation_class=automation,
        gateway_provenance_verified=verified,
        registry_binding_verified=True,
    )
    return lambda _: receipt, lambda _: binding


def review(automation="suspected_human", binding=BINDING, verified=True, events=None):
    gateway, registry = receipts(automation, binding, verified)
    return review_offline_click_receipts(
        events if events is not None else [EVENT],
        resolve_server_receipt=gateway, resolve_private_link_binding=registry,
        secret=KEY, now=NOW + timedelta(minutes=2),
    )


def test_signed_token_is_opaque_and_proves_no_click_or_human():
    token = link()
    assert token.startswith("ecc1." + NONCE)
    for forbidden in (BINDING.tenant_ref, BINDING.campaign_id, BINDING.link_id,
                      BINDING.recipient_lookup_key, BINDING.destination_path, "@"):
        assert forbidden not in token
    assert token_nonce_untrusted(token) == NONCE
    proof = verify_offline_link_token(token, BINDING, secret=KEY, now=NOW)
    assert proof["signature_verified"] is True
    assert all(value is False for name, value in proof.items() if name != "signature_verified")


def test_tampering_or_wrong_private_registry_mapping_fails():
    token = link()
    with pytest.raises(ClickEvidenceHeld, match="SIGNATURE"):
        verify_offline_link_token(token[:-1] + ("A" if token[-1] != "A" else "B"), BINDING, secret=KEY, now=NOW)
    with pytest.raises(ClickEvidenceHeld, match="SIGNATURE"):
        verify_offline_link_token(token, replace(BINDING, recipient_lookup_key="f" * 32), secret=KEY, now=NOW)
    with pytest.raises(ClickEvidenceHeld, match="SIGNATURE"):
        verify_offline_link_token(token, BINDING, secret=b"x" * 32, now=NOW)


def test_reject_before_issue_for_suppressed_or_unknown_contact_permission():
    for permission in ("suppressed", "revoked", "unknown"):
        with pytest.raises(ClickEvidenceHeld, match="PERMISSION"):
            link(replace(BINDING, contact_permission=permission))


def test_expired_future_and_invalid_token_lifetime_are_rejected():
    token = link()
    with pytest.raises(ClickEvidenceHeld, match="OUTSIDE_WINDOW"):
        verify_offline_link_token(token, BINDING, secret=KEY, now=NOW + timedelta(days=2))
    with pytest.raises(ClickEvidenceHeld, match="OUTSIDE_WINDOW"):
        verify_offline_link_token(token, BINDING, secret=KEY, now=NOW - timedelta(seconds=1))
    with pytest.raises(ClickEvidenceHeld, match="TTL"):
        link(end=NOW + timedelta(days=31))


@pytest.mark.parametrize("change", [
    {"destination_path": "https://evil.example/"},
    {"destination_path": "/predictive-revenue?email=person@example.com"},
    {"tenant_ref": "someone@example.com"},
    {"campaign_id": "person@example.com"},
    {"link_id": "link_person"},
    {"recipient_lookup_key": "john@example.com"},
    {"channel": "arbitrary_channel"},
    {"contact_permission": "assumed"},
])
def test_binding_fail_closed_on_unapproved_paths_or_identity(change):
    with pytest.raises(ClickEvidenceHeld):
        link(replace(BINDING, **change))


def test_aggregates_do_not_disclose_any_identity_or_receipts():
    result = review()
    assert result["status"] == "OFFLINE_SIGNED_CLICK_EVIDENCE_REVIEW_ONLY"
    assert result["counts"]["suspected_human_events"] == 1
    assert result["counts"]["followup_review_candidates"] == 1
    for flag in ("live_clicks_verified", "individual_human_identity_verified",
                 "retargeting_consent_verified", "crm_attribution_verified",
                 "realised_revenue_verified", "automatic_followup_enabled",
                 "database_writes", "outbound_sent", "production_click_collector_enabled"):
        assert result[flag] is False
    out = json.dumps(result)
    for private in (NONCE, EVENT, BINDING.tenant_ref, BINDING.campaign_id,
                    BINDING.recipient_lookup_key, link(), "email"):
        assert private not in out


@pytest.mark.parametrize("automation,category", [
    ("scanner", "scanner_excluded_events"), ("uncertain", "uncertain_events"),
    ("suspected_human", "suspected_human_events"),
])
def test_scanners_and_ambiguous_clicks_are_not_hot_leads(automation, category):
    result = review(automation)
    assert result["counts"][category] == 1
    assert result["counts"]["followup_review_candidates"] == (1 if automation == "suspected_human" else 0)


def test_suppression_at_review_time_cannot_create_followup_candidate():
    suppressed = replace(BINDING, contact_permission="suppressed")
    result = review(binding=suppressed)
    assert result["counts"]["permission_held_events"] == 1
    assert result["counts"]["followup_review_candidates"] == 0


def test_duplicate_retry_receipt_is_counted_once():
    result = review(events=[EVENT, EVENT])
    assert result["counts"]["reviewed_events"] == 1
    assert result["counts"]["duplicate_event_ids_discarded"] == 1


def test_absent_gateway_or_unverified_gateway_fails_closed():
    with pytest.raises(ClickEvidenceHeld, match="TRUSTED_GATEWAY"):
        review_offline_click_receipts([EVENT], resolve_server_receipt=None,
                                      resolve_private_link_binding=None, secret=KEY, now=NOW)
    with pytest.raises(ClickEvidenceHeld, match="PROVENANCE"):
        review(verified=False)


def test_wrong_server_receipt_id_and_unverified_registry_are_rejected():
    gateway, registry = receipts()
    altered = replace(gateway(EVENT), gateway_event_id="f" * 32)
    with pytest.raises(ClickEvidenceHeld, match="PROVENANCE"):
        review_offline_click_receipts([EVENT], resolve_server_receipt=lambda _: altered,
             resolve_private_link_binding=registry, secret=KEY, now=NOW + timedelta(minutes=2))
    altered = replace(gateway(EVENT), registry_binding_verified=False)
    with pytest.raises(ClickEvidenceHeld, match="PROVENANCE"):
        review_offline_click_receipts([EVENT], resolve_server_receipt=lambda _: altered,
             resolve_private_link_binding=registry, secret=KEY, now=NOW + timedelta(minutes=2))


def test_unknown_classifier_and_stale_receipts_fail_closed():
    gateway, registry = receipts()
    for receipt in (replace(gateway(EVENT), automation_class="bot_maybe"),
                    replace(gateway(EVENT), observed_at=NOW - timedelta(hours=50))):
        with pytest.raises(ClickEvidenceHeld):
            review_offline_click_receipts([EVENT], resolve_server_receipt=lambda _: receipt,
                resolve_private_link_binding=registry, secret=KEY, now=NOW + timedelta(minutes=2))


def test_resolver_exceptions_do_not_leak_personal_data():
    def broken(_):
        raise RuntimeError("person@example.com")
    with pytest.raises(ClickEvidenceHeld, match="CLICK_SERVER_EVIDENCE_UNAVAILABLE") as exc:
        review_offline_click_receipts([EVENT], resolve_server_receipt=broken,
            resolve_private_link_binding=lambda _: BINDING, secret=KEY, now=NOW)
    assert "person@example.com" not in str(exc.value)


def test_batch_boundaries_are_enforced():
    with pytest.raises(ClickEvidenceHeld, match="TRUSTED_GATEWAY"):
        review(events=[EVENT] * (MAX_BATCH + 1))
    with pytest.raises(ClickEvidenceHeld, match="TRUSTED_GATEWAY"):
        review(events=[])


def test_unsuitable_keys_and_malformed_token_fail():
    with pytest.raises(ClickEvidenceHeld, match="KEY"):
        link(key=b"weak")
    with pytest.raises(ClickEvidenceHeld, match="MALFORMED"):
        token_nonce_untrusted("https://evil.example/?id=someone")
    with pytest.raises(ClickEvidenceHeld, match="NONCE"):
        link(nonce="0" * 32)


def test_multi_asset_engagement_is_grouped_privately_without_identity_leakage():
    second_binding = replace(BINDING, link_id="link_" + "f" * 24)
    second_nonce, second_event = "1" * 32, "2" * 32
    first_gateway, _ = receipts()
    r1 = first_gateway(EVENT)
    r2 = replace(
        r1, gateway_event_id=second_event,
        link_token=link(second_binding, nonce=second_nonce),
        observed_at=NOW + timedelta(minutes=3),
    )
    gateways = {EVENT: r1, second_event: r2}
    bindings = {NONCE: BINDING, second_nonce: second_binding}
    report = review_offline_click_receipts(
        [EVENT, second_event, EVENT],
        resolve_server_receipt=lambda event: gateways[event],
        resolve_private_link_binding=lambda nonce: bindings[nonce],
        secret=KEY, now=NOW + timedelta(minutes=4),
    )
    assert report["counts"]["suspected_human_events"] == 2
    assert report["counts"]["multi_asset_review_groups"] == 1
    assert report["counts"]["duplicate_event_ids_discarded"] == 1
    assert BINDING.recipient_lookup_key not in json.dumps(report)
    # Two clicks on the SAME asset are not misrepresented as multi-asset intent.
    bindings[second_nonce] = BINDING
    r2 = replace(r2, link_token=link(BINDING, nonce=second_nonce))
    gateways[second_event] = r2
    no_multi = review_offline_click_receipts(
        [EVENT, second_event],
        resolve_server_receipt=lambda event: gateways[event],
        resolve_private_link_binding=lambda nonce: bindings[nonce],
        secret=KEY, now=NOW + timedelta(minutes=4),
    )
    assert no_multi["counts"]["multi_asset_review_groups"] == 0
