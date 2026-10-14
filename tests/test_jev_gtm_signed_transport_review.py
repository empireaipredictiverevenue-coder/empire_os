"""First-party signed SMTP observation proof: independent key, replay, expiry, binding."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import base64
import json
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.jev_gtm_mailbox_header_review import _reference
from empire_os.jev_gtm_signed_transport_review import (
    DOMAIN, inspect_signed_ingress_receipts, ISSUER, AUDIENCE, SCHEMA,
)

NOW = datetime(2026, 10, 14, 11, tzinfo=timezone.utc)
TENANT = str(UUID(int=1))
OTHER_TENANT = str(UUID(int=5))
INTENT = str(UUID(int=2))
EVENT = str(UUID(int=3))
REPLY_RFC = "<reply@buyer.example>"
PARENT_RFC = "<sent@mail.empire-ai.co.uk>"
KEY = b"RECONCILIATION_TEST_ONLY_123456789abcdef"
SIGNER = Ed25519PrivateKey.generate()
TRUST = {"owned-mail-ingress-v1": SIGNER.public_key()}
CLAIMS = {
    "issuer": ISSUER,
    "audience": AUDIENCE,
    "event_id": EVENT,
    "tenant_id": TENANT,
    "intent_id": INTENT,
    "message_id": REPLY_RFC,
    "in_reply_to": PARENT_RFC,
    "received_at": int(NOW.timestamp()) - 100,
    "issued_at": int(NOW.timestamp()) - 99,
    "boundary": "first_party_smtp_ingress",
    "direction": "inbound",
    "smtp_result": "dmarc_aligned_pass",
    "raw_message_sha256": sha256(b"fictional fixture mail bytes").hexdigest(),
}


def review(*, duplicates=False, structural=True):
    item = {
        "record_ref": _reference("imap:inbox:77:4", KEY),
        "inbound_rfc_ref": _reference(REPLY_RFC, KEY),
        "rfc_parent_ref": _reference(PARENT_RFC, KEY),
        "intent_alias_ref": _reference(INTENT, KEY),
        "sent_rfc_parent_unique": structural,
        "structural_match_not_authentication": structural,
        "status": "STRUCTURAL_REVIEW_ONLY" if structural else "QUARANTINED",
        "blockers": [
            "ORIGINAL_PROVIDER_AUTHENTICATION_NOT_ATTESTED",
            "CANONICAL_TENANT_CONTACT_BINDING_NOT_ATTESTED",
        ],
        "original_provider_authenticated": False,
        "canonical_contact_verified": False,
        "tenant_binding_verified": False,
        "positive_buyer_intent_verified": False,
        "outbound_authorized": False,
    }
    return {
        "schema_version": "empire.jev.owned_mailbox_header_review.v1",
        "mode": "OBSERVE",
        "provider": "owned_imap",
        "execution_authority": "none",
        "provider_receipts_authenticated": False,
        "canonical_identity_authenticated": False,
        "outbound_authorized": False,
        "commercial_buyer_reply_count": None,
        "rows": [item, dict(item)] if duplicates else [item],
    }


def envelope(*, signer=SIGNER, claims=None, key_id="owned-mail-ingress-v1"):
    payload = CLAIMS if claims is None else claims
    blob = DOMAIN + json.dumps(
        payload, separators=(",", ":"), sort_keys=True,
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    sig = base64.urlsafe_b64encode(signer.sign(blob)).rstrip(b"=").decode("ascii")
    return {
        "schema_version": SCHEMA, "key_id": key_id,
        "claims": dict(payload), "signature": sig,
    }


def inspect(batch=None, *, rows=None, keys=None, now=NOW, tenant=TENANT, key=KEY):
    return inspect_signed_ingress_receipts(
        review() if rows is None else rows,
        [envelope()] if batch is None else batch,
        expected_tenant_id=tenant,
        pinned_ingress_keys=TRUST if keys is None else keys,
        operator_hmac_key=key,
        as_of=now,
    )


def test_independently_pinned_valid_signature_matches_hmac_rfc_triplet_only():
    packet = inspect()
    assert packet["signed_receipts_examined"] == 1
    assert packet["signed_assertions_matched_to_imap_headers"] == 1
    assert packet["rows"][0]["signed_transport_assertion_valid"] is True
    assert packet["rows"][0]["mailbox_rfc_chain_structurally_matched"] is True
    assert packet["trusted_ingress_producer_live_deployment_audited"] is False
    assert packet["original_smtp_provider_authentication_independently_proven"] is False
    assert packet["canonical_tenant_contact_binding_verified"] is False
    assert packet["buyer_reply_count_verified"] is None
    assert packet["recognized_revenue"] is None
    assert packet["suppression_clearance_verified"] is False
    assert packet["outbound_authorized"] is False
    assert packet["execution_authority"] == "none"
    for sensitive in (REPLY_RFC, PARENT_RFC, INTENT, TENANT, KEY.decode()):
        assert sensitive not in repr(packet)


def test_no_signing_key_in_runtime_cannot_fabricate_provenance():
    with pytest.raises(ValueError, match="pinned"):
        inspect(keys={})


def test_unknown_or_rotated_key_id_rejected():
    with pytest.raises(ValueError, match="untrusted"):
        inspect([envelope(key_id="unknown-key")])


def test_wrong_signer_rejected_even_if_claims_are_plausible():
    with pytest.raises(ValueError, match="signature verification failed"):
        inspect([envelope(signer=Ed25519PrivateKey.generate())])


def test_signed_scope_mismatch_cannot_cross_tenants():
    with pytest.raises(ValueError, match="tenant assertion mismatch"):
        inspect(tenant=OTHER_TENANT)


def test_signed_sender_asserted_scope_does_not_override_binding():
    altered = dict(CLAIMS, tenant_id=OTHER_TENANT)
    with pytest.raises(ValueError, match="tenant assertion mismatch"):
        inspect([envelope(claims=altered)])


@pytest.mark.parametrize("modification", [
    {"issuer": "attacker"},
    {"audience": "empire-revenue-crm"},
    {"boundary": "untrusted_imap_header"},
    {"direction": "outbound"},
    {"smtp_result": "dmarc_fail"},
    {"received_at": "yesterday"},
    {"issued_at": int(NOW.timestamp()) + 200},
    {"received_at": int(NOW.timestamp()) - 1000},
    {"received_at": int(NOW.timestamp()) + 200},
    {"in_reply_to": REPLY_RFC},
    {"message_id": "forged-no-rfc"},
    {"raw_message_sha256": "sha256:fake"},
])
def test_signed_receipt_semantics_cannot_assert_disallowed_evidence(modification):
    tampered = dict(CLAIMS, **modification)
    with pytest.raises(ValueError):
        inspect([envelope(claims=tampered)])


def test_expired_original_transport_receipts_not_promoted():
    with pytest.raises(ValueError, match="stale"):
        inspect(now=NOW + timedelta(days=8))


def test_changed_payload_with_original_signature_fails():
    signed = envelope()
    signed["claims"]["smtp_result"] = "dmarc_fail"
    with pytest.raises(ValueError, match="signature"):
        inspect([signed])


def test_duplicate_event_replay_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        inspect([envelope(), envelope()])


def test_signed_same_message_with_competing_event_uuid_rejected():
    another = dict(CLAIMS, event_id=str(UUID(int=88)))
    with pytest.raises(ValueError, match="multiple signed attestations"):
        inspect([envelope(), envelope(claims=another)])


def test_wrong_message_or_intent_does_not_match_header():
    for field, bad in (
        ("message_id", "<other@buyer.example>"),
        ("in_reply_to", "<other@empire.example>"),
        ("intent_id", str(UUID(int=999))),
    ):
        packet = inspect([envelope(claims=dict(CLAIMS, **{field: bad}))])
        assert packet["signed_assertions_matched_to_imap_headers"] == 0
        assert packet["unmatched_signed_assertions"] == 1
        assert packet["buyer_reply_count_verified"] is None


def test_duplicate_mailbox_headers_do_not_grant_attestation_match():
    packet = inspect(rows=review(duplicates=True))
    assert packet["signed_assertions_matched_to_imap_headers"] == 0
    assert packet["unmatched_signed_assertions"] == 1


def test_nonunique_sent_parent_not_counted():
    packet = inspect(rows=review(structural=False))
    assert packet["signed_assertions_matched_to_imap_headers"] == 0


def test_producer_cannot_self_promote_source_fields():
    packet = review()
    packet["rows"][0]["original_provider_authenticated"] = True
    with pytest.raises(ValueError, match="forged"):
        inspect(rows=packet)


def test_empty_signed_receipt_batch_is_unknown_not_zero_buyers():
    packet = inspect([])
    assert packet["signed_receipts_examined"] == 0
    assert packet["signed_assertions_matched_to_imap_headers"] == 0
    assert packet["buyer_reply_count_verified"] is None
    assert packet["trusted_ingress_producer_live_deployment_audited"] is False


def test_receipt_and_review_bounds_fail_closed():
    with pytest.raises(ValueError, match="bounded"):
        inspect([envelope()] * 26)
    with pytest.raises(ValueError, match="bounded"):
        inspect(rows={**review(), "rows": review()["rows"] * 26})


def test_unsigned_mime_authentication_results_cannot_create_receipt():
    with pytest.raises(ValueError, match="malformed"):
        inspect([{"Authentication-Results": "mx.google.com; dmarc=pass"}])


def test_bounded_key_id_is_pinned_only():
    with pytest.raises(ValueError, match="identifier"):
        inspect(keys={"evil/unsafe": SIGNER.public_key()})


def test_wrong_hmac_key_cannot_match_even_authentic_signature():
    packet = inspect(key=b"independent HMAC operator key SECOND_0000000")
    assert packet["signed_assertions_matched_to_imap_headers"] == 0
