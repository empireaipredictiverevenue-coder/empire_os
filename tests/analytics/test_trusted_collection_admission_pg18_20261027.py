"""Isolated PG18 integration of HELD first-party admission with original 054/055.

All claims and keys are synthetic; the production database is not accessed.
This tests server-keyed attribution/consent -> actual original schema triggers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import psycopg
import pytest

from empire_os.analytics.trusted_collection_admission import (
    TrustedCollectionAdmission, AdmissionHeld, PROPERTY, PURPOSE, SCHEMA,
    SESSION_SQL, CONSENT_SQL, EVENT_SQL,
)
from tests.analytics.test_analytics_erasure_pg18_20261019 import held_db
from tests.analytics.test_analytics_ledger_pg18_20261019 import (
    db_socket, TENANT_A, TENANT_B,
)

POLICY = "analytics-test-policy-v1"
SOURCE_SIGNER = Ed25519PrivateKey.from_private_bytes(b"s" * 32)
CMP_SIGNER = Ed25519PrivateKey.from_private_bytes(b"c" * 32)
SOURCE_KEY = SOURCE_SIGNER.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
CMP_KEY = CMP_SIGNER.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
EVENT_KEY = b"e" * 32
SESSION_KEY = b"t" * 32
SESSION_TOKEN = b"n" * 32
PAGES = frozenset({"home", "commercial"})
NOW = datetime.now(timezone.utc)


def gate(*, tenant=TENANT_A, approved=True, source_key=SOURCE_KEY,
         cmp_key=CMP_KEY, event_key=EVENT_KEY, session_key=SESSION_KEY,
         pages=PAGES) -> TrustedCollectionAdmission:
    return TrustedCollectionAdmission(
        tenant_id=tenant, acquisition_verify_public_key=source_key,
        consent_verify_public_key=cmp_key, event_digest_key=event_key,
        session_digest_key=session_key, approved_page_keys=pages,
        policy_revision=POLICY, verified_owner_config=approved,
    )


def _sign(fields: dict, *, key: Ed25519PrivateKey, purpose: bytes) -> dict:
    data = {**fields, "schema": SCHEMA}
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return {
        **data,
        "signature": key.sign(purpose + b":" + canonical).hex(),
    }


def source(*, tenant=TENANT_A, session=None, channel="organic_search",
           evidence="server_verified_referral", when=None,
           source_key=SOURCE_SIGNER):
    return _sign({
        "tenant_id": tenant, "property_key": PROPERTY,
        "session_digest": session or gate(tenant=tenant).derive_session_digest(SESSION_TOKEN),
        "policy_revision": POLICY, "channel": channel,
        "evidence_kind": evidence,
        "issued_at": int((when or NOW).timestamp()),
    }, key=source_key, purpose=b"empire-source-054")


def consent(*, session, tenant=TENANT_A, decision="granted",
            revision=1, when=None, cmp_key=CMP_SIGNER):
    return _sign({
        "tenant_id": tenant, "property_key": PROPERTY,
        "session_digest": session,
        "policy_revision": POLICY, "purpose": PURPOSE,
        "decision": decision, "revision": revision,
        "evidence_digest": uuid4().hex * 2,
        "issued_at": int((when or NOW).timestamp()),
    }, key=cmp_key, purpose=b"empire-cmp-054")


def test_candidate_has_no_db_keys_or_automatic_collector():
    state = TrustedCollectionAdmission.readiness()
    assert state["website_collector_active"] is False
    assert state["runtime_writer_provisioned"] is False
    assert state["analytics075_activated"] is False
    assert state["independent_cmp_legal_consent_proven"] is False
    assert state["execution_authority"] == "NONE"
    with pytest.raises(AdmissionHeld, match="ORIGINAL_OWNER_CONFIG"):
        gate(approved=False)
    for bad in (b"", b"abc", "password", None):
        with pytest.raises(AdmissionHeld):
            gate(source_key=bad)
    with pytest.raises(AdmissionHeld, match="SEPARATE_OWNER_KEY"):
        gate(source_key=CMP_KEY)


def test_signed_owner_envelopes_are_tenant_and_policy_bound():
    a = gate()
    receipt = source()
    assert a.prepare_session(receipt, session_token=SESSION_TOKEN, now=NOW)[3:] == (
        "organic_search", "server_verified_referral", POLICY,
    )
    assert a.prepare_session(receipt, session_token=SESSION_TOKEN, now=NOW)[2] == receipt["session_digest"]
    assert a.derive_session_digest(SESSION_TOKEN) != gate(tenant=TENANT_B).derive_session_digest(SESSION_TOKEN)
    with pytest.raises(AdmissionHeld, match="SESSION_PROOF_NOT_BOUND"):
        a.prepare_session(source(session="f" * 64), session_token=SESSION_TOKEN, now=NOW)
    with pytest.raises(AdmissionHeld, match="SERVER_SESSION_TOKEN"):
        a.derive_session_digest(b"client-supplied-bad")
    with pytest.raises(AdmissionHeld, match="ORIGINAL_OWNER_PAGE_REGISTRY"):
        gate(pages=frozenset())
    for name, value in [
        ("tenant_id", TENANT_B),
        ("property_key", "other.example"),
        ("session_digest", "f" * 64),
        ("channel", "paid_search"),
        ("evidence_kind", "server_unknown"),
        ("policy_revision", "different-policy"),
        ("issued_at", int(NOW.timestamp()) + 10000),
        ("signature", "a" * 64),
        ("email", "private@example.invalid"),
        ("referrer", "https://example.com/?private=value"),
        ("ip", "192.0.2.1"),
    ]:
        bad = dict(receipt)
        bad[name] = value
        with pytest.raises(AdmissionHeld):
            a.prepare_session(bad, session_token=SESSION_TOKEN, now=NOW)
    # Another company's receipt can be cryptographically valid but must
    # still fail against this operator's independently bound tenant.
    with pytest.raises(AdmissionHeld, match="TENANT_PROPERTY"):
        a.prepare_session(source(tenant=TENANT_B), session_token=SESSION_TOKEN, now=NOW)


def test_signed_cmp_receipt_requires_different_independent_authority():
    a = gate()
    s = source()["session_digest"]
    good = consent(session=s)
    assert a.prepare_consent(good, now=NOW)[3:6] == (1, "granted", POLICY)
    with pytest.raises(AdmissionHeld, match="SIGNATURE"):
        a.prepare_consent(
            consent(session=s, cmp_key=SOURCE_SIGNER), now=NOW)
    for field, value in [
        ("decision", "purchased"),
        ("revision", True),
        ("revision", 0),
        ("purpose", "marketing_email"),
        ("tenant_id", TENANT_B),
        ("session_digest", "e" * 64),
        ("evidence_digest", "bad"),
        ("policy_revision", "other-policy"),
        ("email", "private@example.invalid"),
    ]:
        changed = dict(good)
        changed[field] = value
        with pytest.raises(AdmissionHeld):
            a.prepare_consent(changed, now=NOW)
    with pytest.raises(AdmissionHeld, match="EVIDENCE_EXPIRED"):
        a.prepare_consent(
            consent(session=s, when=NOW-timedelta(minutes=4)),
            now=NOW,
        )


def test_evidence_ttl_and_origin_domain_are_strict():
    a = gate()
    with pytest.raises(AdmissionHeld, match="EVIDENCE_EXPIRED"):
        a.prepare_session(
            source(when=NOW-timedelta(minutes=10)), session_token=SESSION_TOKEN, now=NOW)
    with pytest.raises(AdmissionHeld, match="EVIDENCE_EXPIRED"):
        a.prepare_session(
            source(when=NOW+timedelta(minutes=1)), session_token=SESSION_TOKEN, now=NOW)
    src = source()
    raw = {k: v for k, v in src.items() if k != "signature"}
    wrongly_signed = _sign(raw, key=SOURCE_SIGNER, purpose=b"empire-cmp-054")
    with pytest.raises(AdmissionHeld, match="SIGNATURE"):
        a.prepare_session(wrongly_signed, session_token=SESSION_TOKEN, now=NOW)


def test_event_whitelist_and_tenant_keyed_replay_digests():
    a = gate()
    s = source()["session_digest"]
    values = dict(session_digest=s, event_nonce=uuid4().hex,
                  event_kind="cta_click", page_key="commercial",
                  occurred_at=NOW, now=NOW)
    proof = a.prepare_event(**values)
    assert len(proof) == 7
    assert proof[0] == TENANT_A and proof[1] == PROPERTY
    assert proof[4:6] == ("cta_click", "commercial")
    assert proof == a.prepare_event(**values)
    other = gate(tenant=TENANT_B)
    assert proof[2] != other.prepare_event(**values)[2]
    for field, value in [
        ("event_nonce", "not-a-nonce"),
        ("event_nonce", "UPPERCASE"),
        ("event_kind", "purchase"),
        ("event_kind", "form_submit_confirmed"),
        ("page_key", "/commercial?utm_person=secret"),
        ("page_key", "john@example.com"),
        ("page_key", "x" * 100),
        ("page_key", "visitor_name"),  # syntactically safe, NOT owner allowlisted
        ("session_digest", "bad"),
        ("occurred_at", NOW-timedelta(minutes=7)),
        ("occurred_at", NOW+timedelta(minutes=1)),
    ]:
        bad = dict(values, **{field: value})
        with pytest.raises(AdmissionHeld):
            a.prepare_event(**bad)


def test_original_pg18_ledger_real_inserts_and_revocation(held_db):
    dsn, _, _ = held_db
    a = gate()
    src = source(channel="email", evidence="signed_campaign_binding")
    session = src["session_digest"]
    with psycopg.connect(dsn, autocommit=True) as conn:
        # This is only the disposable fixture admin, never a production writer.
        conn.execute(SESSION_SQL, a.prepare_session(src, session_token=SESSION_TOKEN, now=NOW))
        evt = a.prepare_event(
            session_digest=session, event_nonce=uuid4().hex,
            event_kind="page_view", page_key="home",
            occurred_at=datetime.now(timezone.utc), now=datetime.now(timezone.utc),
        )
        with pytest.raises(psycopg.Error, match="WEBSITE_CONSENT_NOT_PROVEN"):
            conn.execute(EVENT_SQL, evt)
        denied = consent(session=session, decision="denied")
        conn.execute(CONSENT_SQL, a.prepare_consent(denied, now=NOW))
        with pytest.raises(psycopg.Error, match="WEBSITE_CONSENT_NOT_PROVEN"):
            conn.execute(EVENT_SQL, evt)
        grant = consent(session=session, decision="granted", revision=2)
        conn.execute(CONSENT_SQL, a.prepare_consent(grant, now=NOW))
        # Generate event only AFTER the database's actual consent timestamp.
        event = a.prepare_event(
            session_digest=session, event_nonce=uuid4().hex,
            event_kind="cta_click", page_key="commercial",
            occurred_at=datetime.now(timezone.utc), now=datetime.now(timezone.utc),
        )
        conn.execute(EVENT_SQL, event)
        with pytest.raises(psycopg.Error, match="duplicate key"):
            conn.execute(EVENT_SQL, event)
        with pytest.raises(psycopg.Error):
            conn.execute(EVENT_SQL, (*event[:3], "f" * 64, *event[4:]))
        revoked = consent(session=session, decision="revoked", revision=3)
        conn.execute(CONSENT_SQL, a.prepare_consent(revoked, now=NOW))
        with pytest.raises(psycopg.Error, match="WEBSITE_CONSENT_NOT_PROVEN"):
            conn.execute(EVENT_SQL, a.prepare_event(
                session_digest=session, event_nonce=uuid4().hex,
                event_kind="engagement", page_key="home",
                occurred_at=datetime.now(timezone.utc),
                now=datetime.now(timezone.utc),
            ))
        with pytest.raises(psycopg.Error, match="INVALID_CONSENT_TRANSITION"):
            conn.execute(CONSENT_SQL, a.prepare_consent(
                consent(session=session, decision="granted", revision=4),
                now=NOW,
            ))
        exact = conn.execute("""
            SELECT count(*) FROM public.empire_analytics_event_receipts
            WHERE tenant_id=%s AND property_key=%s AND session_digest=%s
        """, (TENANT_A, PROPERTY, session)).fetchone()[0]
        assert exact == 1


def test_fixture_post_055_public_cannot_read_or_ingest(held_db):
    dsn, _, _ = held_db
    with psycopg.connect(dsn, autocommit=True) as db:
        for name in ("sessions", "consent_decisions", "event_receipts"):
            assert db.execute(
                "SELECT has_table_privilege('public', %s,'INSERT')",
                ("public.empire_analytics_" + name,),
            ).fetchone()[0] is False
            assert db.execute(
                "SELECT has_table_privilege('public', %s,'SELECT')",
                ("public.empire_analytics_" + name,),
            ).fetchone()[0] is False
        assert db.execute("""
            SELECT count(*) FROM pg_catalog.pg_roles
            WHERE rolname IN ('empire_analytics_collection_login',
                              'empire_analytics_maintenance_login')
        """).fetchone()[0] == 0
