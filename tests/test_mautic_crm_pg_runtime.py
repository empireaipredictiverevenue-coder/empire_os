"""Real PostgreSQL integration tests, only via isolated disposable cluster.

Run using scripts/test_mautic_crm_pg_isolated.sh; never against live EmpireDB.
The fixture uses synthetic data, private Unix sockets and dedicated roles.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.mautic_crm_inbox import (
    MauticInboxUnavailable, PostgresMauticEventInbox,
)
from empire_os.mautic_crm_integration import MauticSource, create_mautic_crm_preview_router
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

if os.environ.get("PGDATABASE") != "mautic_crm_inbox_fixture":
    pytest.skip("isolated disposable PostgreSQL fixture required", allow_module_level=True)

TENANT_A = "00000000-0000-0000-0000-000000000101"
TENANT_B = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
NOW = datetime(2026, 11, 19, 11, tzinfo=timezone.utc)
SECRET = b"mautic-only-synthetic-fixture-secret"
BASE = "/v1/revenue-crm/integrations/mautic/fixture-7/events/preview"


def dsn(user: str) -> str:
    assert os.environ["PGHOST"].startswith("/tmp/empire_mautic_pg_fixture.")
    assert os.environ["PGPORT"] == "55488"
    return (
        f"dbname=mautic_crm_inbox_fixture user={user} "
        f"host={os.environ['PGHOST']} port=55488 connect_timeout=3"
    )


def writer(user="mautic_fixture_writer_a", tenant=TENANT_A):
    return PostgresMauticEventInbox(dsn(user), authenticated_tenant_id=tenant)


def reader():
    return PostgresRevenueCrmRepository(
        dsn("mautic_fixture_reader_a"), tenant_id=TENANT_A
    )


def review(event_hash="a" * 64, prospect=PROSPECT):
    return {
        "prospect_id": prospect,
        "event_evidence_hmac": event_hash,
        "source_event": "mautic.lead_channel_subscription_changed",
        "signal": "SUPPRESSION_REVIEW_REQUIRED",
        "timestamp_state": "RECENT_OBSERVED",
        "canonical_journey_segment": "contact_hold",
    }


def test_postgres_dedicated_role_and_canonical_readback_idempotency():
    token = "a" * 64
    result = writer().reserve_new(
        tenant_id=TENANT_A, source_id="fixture-7",
        evidence_hmacs=[token], reviews=[review(token)], now=NOW
    )
    assert result == {token}
    assert writer().reserve_new(
        tenant_id=TENANT_A, source_id="fixture-7",
        evidence_hmacs=[token], reviews=[review(token)], now=NOW
    ) == set()
    with psycopg.connect(dsn("mautic_fixture_writer_a")) as con:
        with con.cursor() as cur:
            cur.execute("SELECT session_user, current_user")
            assert cur.fetchone() == ("mautic_fixture_writer_a", "mautic_fixture_writer_a")
            cur.execute("SET LOCAL ROLE empire_mautic_crm_inbox_writer")
            cur.execute("SELECT public.empire_current_tenant_id()::text")
            assert cur.fetchone() == (TENANT_A,)
            cur.execute(
                "SELECT count(*) FROM public.empire_crm_mautic_event_inbox "
                "WHERE tenant_id=%s::uuid", (TENANT_A,)
            )
            assert cur.fetchone() == (1,)


def test_real_row_level_security_hides_other_tenant_rows_and_denies_writes():
    # Different dedicated session_user must not see A's row.
    with psycopg.connect(dsn("mautic_fixture_writer_b")) as con:
        with con.cursor() as cur:
            cur.execute("SET LOCAL ROLE empire_mautic_crm_inbox_writer")
            cur.execute("SELECT count(*) FROM public.empire_crm_mautic_event_inbox")
            assert cur.fetchone() == (0,)
    # RLS blocks cross-tenant INSERT, even if API caller provides another ID.
    with pytest.raises(psycopg.Error):
        with psycopg.connect(dsn("mautic_fixture_writer_a")) as con:
            with con.cursor() as cur:
                cur.execute("SET LOCAL ROLE empire_mautic_crm_inbox_writer")
                cur.execute(
                    "INSERT INTO public.empire_crm_mautic_event_inbox "
                    "(tenant_id,source_id,event_evidence_hmac,prospect_id,"
                    "source_event,review_signal,timestamp_state,journey_segment)"
                    "VALUES (%s::uuid,'fixture-7',%s,%s::uuid,"
                    "'mautic.form_on_submit','FORM_SUBMISSION_REVIEW_NOT_CONSENT',"
                    "'RECENT_OBSERVED','contact_hold')",
                    (TENANT_B,"b"*64,PROSPECT),
                )
    # Tenant writer cannot silently modify or delete append-only evidence.
    with pytest.raises(psycopg.Error):
        with psycopg.connect(dsn("mautic_fixture_writer_a")) as con:
            with con.cursor() as cur:
                cur.execute("SET LOCAL ROLE empire_mautic_crm_inbox_writer")
                cur.execute(
                    "DELETE FROM public.empire_crm_mautic_event_inbox"
                )


def test_actual_tenant_bound_smart_crm_reader_and_no_foreign_prospect():
    repo = reader()
    row = repo.prospect(PROSPECT)
    assert row is not None
    assert str(row["tenant_id"]) == TENANT_A
    assert row["prospect_status"] == "suppressed"
    assert repo.prospect("00000000-0000-0000-0000-000000000202") is None
    # The DB resolver rejects an attacker-chosen tenant, without relaxing RLS.
    with pytest.raises(Exception):
        PostgresRevenueCrmRepository(
            dsn("mautic_fixture_reader_a"), tenant_id=TENANT_B
        ).prospect(PROSPECT)


def test_actual_postgres_http_signed_webhook_to_canonical_inbox_and_replay():
    configured = MauticSource(
        source_id="fixture-7",
        tenant_id=TENANT_A,
        webhook_secret=SECRET,
        contact_bindings={
            42: {"tenant_id": TENANT_A, "prospect_id": PROSPECT}
        },
    )
    app = FastAPI()
    app.include_router(create_mautic_crm_preview_router(
        resolve_source=lambda name: configured if name == "fixture-7" else None,
        resolve_tenant_reader=lambda tenant: reader() if tenant == TENANT_A else None,
        receipt_journal=writer(),
        now_provider=lambda: NOW,
    ))
    payload = {
        "mautic.lead_channel_subscription_changed": [
            {
                "contact": {"id":42,"email":"hidden+test@example.invalid"},
                "channel":"email","new_status":"unsubscribed",
                "timestamp":NOW.isoformat(),
            }
        ]
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = base64.b64encode(hmac.new(SECRET,raw,hashlib.sha256).digest()).decode()
    headers = {"Content-Type":"application/json","Webhook-Signature":signature}
    with TestClient(app) as client:
        first = client.post(BASE,content=raw,headers=headers)
        assert first.status_code == 200, first.text
        result = first.json()
        assert result["new_events"] == 1
        assert result["canonical_inbox_readback_verified"]
        assert result["journey_reviews"][0]["canonical_journey_segment"] == "contact_hold"
        assert result["journey_reviews"][0]["send_authorized"] is False
        assert result["canonical_crm_written"] is False
        assert "hidden+test@example.invalid" not in first.text
        second = client.post(BASE,content=raw,headers=headers)
        assert second.status_code == 200
        assert second.json()["new_events"] == 0
        assert second.json()["duplicate_events"] == 1
        assert client.post(BASE,content=raw+b" ",headers=headers).status_code == 401
        # An unmapped Mautic contact must receive retryable failure, not 2xx.
        payload["mautic.lead_channel_subscription_changed"][0]["contact"]["id"] = 999
        unbound = json.dumps(payload,separators=(",", ":")).encode("utf-8")
        new_sig = base64.b64encode(hmac.new(SECRET,unbound,hashlib.sha256).digest()).decode()
        failed = client.post(BASE,content=unbound,headers={
            "Content-Type":"application/json","Webhook-Signature":new_sig
        })
        assert failed.status_code == 503


def test_authenticated_existing_crm_reads_durable_mautic_inbox_without_sender_rights():
    from empire_os.mautic_crm_review_api import create_mautic_crm_review_router
    from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead

    # This event is not injected into the CRM; it stays review-only in
    # the canonical event inbox. The synthetic reader is a real dedicated
    # PostgreSQL login to the disposable fixture database.
    fingerprint = "c" * 64
    writer().reserve_new(
        tenant_id=TENANT_A, source_id="fixture-7",
        evidence_hmacs=[fingerprint],
        reviews=[review(fingerprint)],
        now=NOW,
    )
    app = FastAPI()
    app.include_router(create_mautic_crm_review_router(
        resolve_authenticated_read=lambda req: (
            AuthenticatedRevenueCrmRead(
                tenant_id=TENANT_A, repository=reader(),
            ) if req.headers.get("authorization") == "Bearer test-local-tenant-only"
            else None
        ),
    ))
    with TestClient(app) as client:
        endpoint = "/v1/revenue-crm/integrations/mautic/inbox/reviews"
        assert client.get(endpoint).status_code == 401
        headers = {"Authorization": "Bearer test-local-tenant-only"}
        response = client.get(endpoint, headers=headers, params={"limit": 5})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["tenant_id"] == TENANT_A
        assert result["mode"] == "OBSERVE"
        assert result["read_only"] is True
        assert result["canonical_crm_written"] is False
        assert result["send_authorized"] is False
        assert result["count"] >= 1
        events = [item for item in result["inbox_events"]
                  if item["event_evidence_hmac"] == fingerprint]
        assert len(events) == 1
        item = events[0]
        assert item["prospect_id"] == PROSPECT
        assert item["review_signal"] == "SUPPRESSION_REVIEW_REQUIRED"
        assert item["journey_segment_at_ingest"] == "contact_hold"
        assert item["execution_authority"] == "none"
        assert item["send_authorized"] is False
        assert item["contact_details_disclosed"] is False
        assert "hidden+test@example.invalid" not in response.text

    # The same existing CRM reader login must never INSERT/UPDATE/DELETE.
    with pytest.raises(psycopg.Error):
        with psycopg.connect(dsn("mautic_fixture_reader_a")) as con:
            with con.cursor() as cur:
                cur.execute("SET LOCAL ROLE empire_revenue_crm_reader")
                cur.execute(
                    "INSERT INTO public.empire_crm_mautic_event_inbox "
                    "(tenant_id,source_id,event_evidence_hmac,prospect_id,"
                    "source_event,review_signal,timestamp_state,journey_segment)"
                    " VALUES (%s::uuid,'fixture-7',%s,%s::uuid,"
                    "'mautic.form_on_submit','FORM_SUBMISSION_REVIEW_NOT_CONSENT',"
                    "'RECENT_OBSERVED','contact_hold')",
                    (TENANT_A, "d" * 64, PROSPECT),
                )


def test_crm_inbox_reader_database_tenant_mismatch_fails_closed():
    from empire_os.mautic_crm_review_api import create_mautic_crm_review_router
    from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead

    bad_repo = PostgresRevenueCrmRepository(
        dsn("mautic_fixture_reader_a"), tenant_id=TENANT_B
    )
    app = FastAPI()
    app.include_router(create_mautic_crm_review_router(
        resolve_authenticated_read=lambda _req: AuthenticatedRevenueCrmRead(
            tenant_id=TENANT_B, repository=bad_repo,
        )
    ))
    response = TestClient(app).get(
        "/v1/revenue-crm/integrations/mautic/inbox/reviews"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "canonical_mautic_inbox_unavailable"


def test_existing_crm_reader_cannot_see_other_tenants_mautic_event_inbox():
    # Tenant B owns a distinct review event. Existing A reader cannot
    # retrieve it even with no explicit WHERE clause: database FORCE RLS.
    token_b = "e" * 64
    prospect_b = "00000000-0000-0000-0000-000000000202"
    PostgresMauticEventInbox(
        dsn("mautic_fixture_writer_b"), authenticated_tenant_id=TENANT_B
    ).reserve_new(
        tenant_id=TENANT_B, source_id="fixture-7",
        evidence_hmacs=[token_b],
        reviews=[review(token_b, prospect=prospect_b)],
        now=NOW,
    )
    with psycopg.connect(dsn("mautic_fixture_reader_a")) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE empire_revenue_crm_reader")
            cur.execute(
                "SELECT event_evidence_hmac FROM public.empire_crm_mautic_event_inbox "
                "WHERE event_evidence_hmac=%s", (token_b,)
            )
            assert cur.fetchall() == []
    # CRM inbox reporting is bound to the same dedicated tenant login;
    # HTTP callers cannot promote a cross-tenant row via query parameters.
