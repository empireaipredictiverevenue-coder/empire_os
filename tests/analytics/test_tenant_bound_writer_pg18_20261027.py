"""Security proof for future Analytics054 tenant-bound writer — isolated PG18 ONLY.

Fixture role, grants and RLS policies NEVER run on production EmpireDB.
No protected login is provisioned and no migration is prepared for deployment.
The original Analytics054/055 trigger contract must pass with an explicit
per-tenant identity; caller-specified PostgreSQL GUCs are not trusted.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import psycopg
import pytest

from tests.analytics.test_analytics_erasure_pg18_20261019 import held_db
from tests.analytics.test_analytics_ledger_pg18_20261019 import (
    db_socket, TENANT_A, TENANT_B, ADMIN, PROP,
)
from empire_os.analytics.trusted_collection_admission import (
    SESSION_SQL, CONSENT_SQL, EVENT_SQL,
)

ROLE = "analytics_fixture_tenant_a_writer"
POLICY = "analytics-fixture-policy-v1"


@pytest.fixture(scope="module")
def isolated_writer(held_db):
    dsn, _, _ = held_db
    with psycopg.connect(dsn, autocommit=True) as admin:
        # This is a fixture-only role, deliberately not the production name.
        admin.execute(
            f"CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT"
        )
        admin.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
        admin.execute(
            f"GRANT INSERT,SELECT,UPDATE "
            f"ON public.empire_analytics_sessions TO {ROLE}"
        )
        admin.execute(
            f"GRANT INSERT,SELECT ON "
            f"public.empire_analytics_consent_decisions TO {ROLE}"
        )
        admin.execute(
            f"GRANT INSERT ON public.empire_analytics_event_receipts TO {ROLE}"
        )
        admin.execute(f"""
            CREATE POLICY fixture_session_insert ON public.empire_analytics_sessions
             FOR INSERT TO {ROLE}
             WITH CHECK (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
        """)
        admin.execute(f"""
            CREATE POLICY fixture_session_select ON public.empire_analytics_sessions
             FOR SELECT TO {ROLE}
             USING (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
        """)
        admin.execute(f"""
            CREATE POLICY fixture_session_update_lock ON public.empire_analytics_sessions
             FOR UPDATE TO {ROLE}
             USING (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
             WITH CHECK (false)
        """)
        admin.execute(f"""
            CREATE POLICY fixture_consent_insert ON public.empire_analytics_consent_decisions
             FOR INSERT TO {ROLE}
             WITH CHECK (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
        """)
        admin.execute(f"""
            CREATE POLICY fixture_consent_select ON public.empire_analytics_consent_decisions
             FOR SELECT TO {ROLE}
             USING (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
        """)
        admin.execute(f"""
            CREATE POLICY fixture_events_insert ON public.empire_analytics_event_receipts
             FOR INSERT TO {ROLE}
             WITH CHECK (tenant_id='{TENANT_A}'::uuid
               AND property_key='empire-ai.co.uk')
        """)
    yield dsn.replace(f"user={ADMIN}", f"user={ROLE}")


def _session(tenant=TENANT_A):
    digest = uuid.uuid4().hex*2
    params = (
        tenant, PROP, digest, "direct", "server_observed_direct", POLICY,
    )
    return digest, params


def _consent(tenant, digest, rev, decision):
    return (
        tenant, PROP, digest, rev, decision, POLICY, uuid.uuid4().hex*2,
    )


def _event(tenant, digest):
    return (
        tenant, PROP, uuid.uuid4().hex*2, digest,
        "cta_click", "home", datetime.now(timezone.utc),
    )


def test_exact_tenant_fixture_can_admit_after_original_consent(isolated_writer):
    with psycopg.connect(isolated_writer, autocommit=True) as writer:
        digest, values = _session()
        writer.execute(SESSION_SQL, values)
        with pytest.raises(psycopg.Error, match="WEBSITE_CONSENT_NOT_PROVEN"):
            writer.execute(EVENT_SQL, _event(TENANT_A, digest))
        writer.execute(CONSENT_SQL, _consent(TENANT_A, digest, 1, "granted"))
        writer.execute(EVENT_SQL, _event(TENANT_A, digest))
        writer.execute(CONSENT_SQL, _consent(TENANT_A, digest, 2, "revoked"))
        with pytest.raises(psycopg.Error, match="WEBSITE_CONSENT_NOT_PROVEN"):
            writer.execute(EVENT_SQL, _event(TENANT_A, digest))
        # Original append-only trigger blocks an UPDATE even if the writer
        # has UPDATE privilege solely to acquire SELECT ... FOR UPDATE locks.
        with pytest.raises(psycopg.Error):
            writer.execute("""
                UPDATE public.empire_analytics_sessions SET policy_revision=policy_revision
                WHERE tenant_id=%s AND property_key=%s AND session_digest=%s
            """, (TENANT_A, PROP, digest))


def test_exact_tenant_fixture_cannot_access_other_tenant(isolated_writer):
    with psycopg.connect(isolated_writer, autocommit=True) as writer:
        other_digest, values = _session(TENANT_B)
        with pytest.raises(psycopg.Error):
            writer.execute(SESSION_SQL, values)
        with pytest.raises(psycopg.Error):
            writer.execute(CONSENT_SQL, _consent(TENANT_B,other_digest,1,"granted"))
        with pytest.raises(psycopg.Error):
            writer.execute(EVENT_SQL, _event(TENANT_B,other_digest))
        assert writer.execute("""
            SELECT count(*) FROM public.empire_analytics_sessions
            WHERE tenant_id=%s
        """, (TENANT_B,)).fetchone()[0] == 0
        # A session SET of an arbitrary tenant configuration cannot bypass
        # a policy that binds identity to the immutable session LOGIN.
        writer.execute("SELECT set_config('empire.analytics_tenant',%s,false)", (TENANT_B,))
        with pytest.raises(psycopg.Error):
            writer.execute(SESSION_SQL, values)


def test_fixture_writer_cannot_reach_maintenance_crm_or_finance(isolated_writer):
    with psycopg.connect(isolated_writer, autocommit=True) as writer:
        for sql in (
            "SET ROLE empiredb_migrator",
            "SELECT count(*) FROM public.empire_analytics_erasure_audit",
            "SELECT count(*) FROM public.empire_analytics_event_receipts",
            "DELETE FROM public.empire_analytics_sessions WHERE false",
            "SELECT public.empire_analytics_erase_session(NULL,NULL,NULL,NULL,NULL)",
        ):
            with pytest.raises(psycopg.Error):
                writer.execute(sql)
    # No fixture role is created in the production DB. No PUBLIC privileges
    # are added; this test is restricted to the original isolated socket.
