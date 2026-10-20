"""Research pickup/owner reply attestation; no real buyers or messages."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from empire_os.a2a_owner_research_protocol_v1 import (
    OUTBOX_SCHEMA, RECEIPT_SCHEMA, make_owner_pickup_packets,
    receipt_signing_bytes, review_owner_receipts,
)
from tests.test_a2a_target_owner_handoff_v1_20261020 import (
    scout, targeting, NOW,
)
from empire_os.a2a_target_owner_handoff_v1 import make_owner_research_handoffs


def pickup():
    return make_owner_pickup_packets(make_owner_research_handoffs(
        targeting(), scout(), now=NOW))


def keys():
    pairs = {name: Ed25519PrivateKey.generate() for name in ("buyer_scout", "community_intent")}
    public = {name: private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    ) for name, private in pairs.items()}
    return pairs, public


def sign(ticket: dict, private: Ed25519PrivateKey, *,
         occurred: datetime = NOW, nonce: str | None = None,
         state: str = "ACCEPTED_FOR_RESEARCH", refs=None) -> dict:
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": ticket["ticket_sha256"],
        "owner": ticket["research_request"]["review_owner"],
        "status": state,
        "occurred_at": occurred.isoformat(),
        "nonce": nonce or secrets.token_urlsafe(30),
        "source_snapshot_sha256": "c" * 64,
        "evidence_reference_ids": refs or [],
        "no_external_outbound": True,
        "execution_authority": "NONE",
        "signature_b64url": "",
    }
    payload = receipt_signing_bytes(receipt)
    receipt["signature_b64url"] = base64.urlsafe_b64encode(
        private.sign(payload)).rstrip(b"=").decode()
    return receipt


def test_stable_owner_pickup_partition_with_no_dispatch():
    first, second = pickup(), pickup()
    assert first == second
    assert first["schema_version"] == OUTBOX_SCHEMA
    assert first["pickup_count"] == 4
    assert len(first["pickup_by_owner"]["buyer_scout"]) == 2
    assert len(first["pickup_by_owner"]["community_intent"]) == 2
    assert first["owner_dispatches"] == 0
    assert first["queue_published_outside_isolated_worktree"] is False
    assert all(row["execution_state"] == "PICKUP_AVAILABLE_NOT_DELIVERED"
               for values in first["pickup_by_owner"].values() for row in values)


def test_signed_ack_is_research_only_not_verified_sale_or_buyer():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["buyer_scout"][0]
    receipt = sign(task, pair["buyer_scout"])
    r = review_owner_receipts(p, [receipt], public, now=NOW)
    assert r["authenticated_owner_replies"] == 1
    assert r["owner_research_accepted"] == 1
    assert r["still_awaiting_authenticated_owner_replies"] == 3
    assert r["buyer_identity_verified_by_this_protocol"] is False
    assert r["purchase_intent_verified_by_this_protocol"] is False
    assert r["owner_task_dispatches_by_this_protocol"] == 0


def test_owner_signature_is_required_not_self_reported_status():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["buyer_scout"][0]
    receipt = sign(task, pair["community_intent"])
    rejected = review_owner_receipts(p, [receipt], public, now=NOW)
    assert rejected["authenticated_owner_replies"] == 0
    assert "INVALID_OWNER_SIGNATURE" in rejected["rejection_reason_codes"]
    blocked = review_owner_receipts(p, [sign(task, pair["buyer_scout"])], {}, now=NOW)
    assert blocked["authenticated_owner_replies"] == 0
    assert "TRUSTED_OWNER_PUBLIC_KEY_NOT_CONFIGURED" in blocked["rejection_reason_codes"]


def test_tamper_and_replay_detection():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["buyer_scout"][0]
    genuine = sign(task, pair["buyer_scout"])
    tampered = deepcopy(genuine)
    tampered["status"] = "DECLINED"
    r = review_owner_receipts(p, [tampered], public, now=NOW)
    assert "INVALID_OWNER_SIGNATURE" in r["rejection_reason_codes"]
    another = p["pickup_by_owner"]["community_intent"][0]
    replay = sign(another, pair["community_intent"],
                  nonce=genuine["nonce"])
    # Nonce namespaces are per-owner, so different owners can use one nonce.
    r = review_owner_receipts(p, [genuine, replay], public, now=NOW)
    assert r["authenticated_owner_replies"] == 2
    another_same_owner = p["pickup_by_owner"]["buyer_scout"][1]
    replay_same_owner = sign(another_same_owner, pair["buyer_scout"],
                             nonce=genuine["nonce"])
    r = review_owner_receipts(p, [genuine, replay_same_owner], public, now=NOW)
    assert r["authenticated_owner_replies"] == 1
    assert "REPLAYED_OWNER_NONCE" in r["rejection_reason_codes"]


def test_future_or_stale_or_unauthorised_ack_rejected():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["buyer_scout"][0]
    old = sign(task, pair["buyer_scout"], occurred=NOW-timedelta(days=5))
    reject = review_owner_receipts(p, [old], public, now=NOW)
    assert "STALE_OR_FUTURE_OWNER_RECEIPT" in reject["rejection_reason_codes"]
    escalated = sign(task, pair["buyer_scout"])
    escalated["execution_authority"] = "PAYMENT"
    reject = review_owner_receipts(p, [escalated], public, now=NOW)
    assert "UNVERIFIED_OWNER_CLAIM" in reject["rejection_reason_codes"]
    evidence = sign(task, pair["buyer_scout"], state="EVIDENCE_REVIEW_AVAILABLE")
    reject = review_owner_receipts(p, [evidence], public, now=NOW)
    assert "EVIDENCE_REF_REQUIRED" in reject["rejection_reason_codes"]


def test_verified_review_ref_not_customer_record():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["community_intent"][1]
    receipt = sign(task, pair["community_intent"],
                   state="EVIDENCE_REVIEW_AVAILABLE",
                   refs=["canonical:source_receipt:public_scope_123"])
    r = review_owner_receipts(p, [receipt], public, now=NOW)
    assert r["owner_evidence_reviews_available"] == 1
    assert r["authenticated_owner_replies"] == 1
    assert not r["buyer_qualified_by_this_protocol"]
    assert "canonical:source_receipt:public_scope_123" not in str(r)


def test_rejects_unknown_receipts_and_untrusted_outbox():
    p = pickup()
    pair, public = keys()
    task = p["pickup_by_owner"]["buyer_scout"][0]
    receipt = sign(task, pair["buyer_scout"])
    forged = deepcopy(receipt)
    forged["ticket_id"] = "0" * 24
    reject = review_owner_receipts(p, [forged], public, now=NOW)
    assert "UNKNOWN_TICKET" in reject["rejection_reason_codes"]
    p["owner_dispatches"] = 1
    with pytest.raises(ValueError, match="untrusted_owner_pickup"):
        review_owner_receipts(p, [receipt], public, now=NOW)
