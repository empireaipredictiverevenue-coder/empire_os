"""Run staged Analytics075 only against an ISOLATED, disposable PG18 fixture.

Reuses Analytics054/055 existing private-socket tests; not production EmpireDB.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import psycopg
import pytest

from tests.analytics.test_analytics_erasure_pg18_20261019 import held_db
from tests.analytics.test_analytics_ledger_pg18_20261019 import (
    new_session, TENANT_A, db_socket,
)

MIGRATION = (Path(__file__).resolve().parents[2] /
             "migrations/empiredb/075_first_party_analytics_source_taxonomy_v2_held.sql")


@pytest.fixture(scope="module")
def v2_db(held_db):
    dsn, _, env = held_db
    cmd = [
        "/usr/lib/postgresql/18/bin/psql", "-X", "-v", "ON_ERROR_STOP=1",
        "-d", "empire_analytics_fixture", "-f", str(MIGRATION),
    ]
    run = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=25)
    if run.returncode:
        with psycopg.connect(dsn, autocommit=True) as db:
            constraints = db.execute(
                "SELECT conname FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.empire_analytics_sessions'::regclass "
                "ORDER BY conname"
            ).fetchall()
        raise AssertionError(run.stderr[-800:] + "\nFOUND_CONSTRAINTS=" +
                             repr([r[0] for r in constraints]))
    return dsn, env


def test_held_sql_v2_transaction_adds_all_five_new_channels_and_preserves_v1(v2_db):
    dsn, _ = v2_db
    with psycopg.connect(dsn, autocommit=True) as db:
        rows = db.execute("""
            SELECT conname, convalidated FROM pg_catalog.pg_constraint
            WHERE conrelid='public.empire_analytics_sessions'::regclass
              AND conname LIKE 'empire_analytics%check'
            ORDER BY conname
        """).fetchall()
        assert ("empire_analytics_source_channel_v2_check", True) in rows
        assert ("empire_analytics_source_evidence_v2_check", True) in rows
        assert not any("sessions_acquisition_channel_check" in name
                       or name == "empire_analytics_sessions_check"
                       for name, _ in rows)
        all_channels = {
            "direct": "server_observed_direct",
            "organic_search": "server_verified_referral",
            "organic_social": "server_verified_referral",
            "referral": "server_verified_referral",
            "email": "signed_campaign_binding",
            "unknown": "server_unknown",
            "paid_search": "signed_campaign_binding",
            "paid_social": "signed_campaign_binding",
            "affiliate_partner": "signed_partner_binding",
            "publisher_referral": "signed_partner_binding",
            "organic_video": "server_verified_referral",
        }
        for channel, proof in all_channels.items():
            new_session(db, tenant=TENANT_A, channel=channel, evidence=proof)


@pytest.mark.parametrize("channel,evidence", [
    ("paid_search", "server_verified_referral"),
    ("affiliate_partner", "signed_campaign_binding"),
    ("publisher_referral", "server_verified_referral"),
    ("organic_video", "signed_campaign_binding"),
    ("paid_social", "server_unknown"),
    ("outbound_phone", "signed_partner_binding"),
    ("organic_search", "signed_campaign_binding"),
])
def test_mismatched_or_unapproved_source_insert_rejected_by_database(v2_db,channel,evidence):
    with psycopg.connect(v2_db[0], autocommit=True) as db:
        with pytest.raises(psycopg.Error):
            new_session(db, tenant=TENANT_A, channel=channel, evidence=evidence)


def test_held_v2_never_creates_login_policy_or_public_session_access(v2_db):
    with psycopg.connect(v2_db[0], autocommit=True) as db:
        rows = db.execute("""
          SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
            AND c.relname IN ('empire_analytics_sessions',
             'empire_analytics_consent_decisions','empire_analytics_event_receipts')
          ORDER BY c.relname
        """).fetchall()
        assert len(rows) == 3
        assert all(row[1:] == (True, True) for row in rows)
        policy_roles = db.execute("""
            SELECT r.rolname FROM pg_catalog.pg_policy p
            JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
            JOIN pg_catalog.pg_roles r ON r.oid = ANY(p.polroles)
            WHERE c.relname='empire_analytics_sessions'
        """).fetchall()
        assert policy_roles and {r[0] for r in policy_roles} == {"empiredb_migrator"}
        assert db.execute("""
            SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
              WHERE rolname='empire_analytics_collection_login')
        """).fetchone()[0] is False
        assert db.execute("""
            SELECT has_table_privilege('public','public.empire_analytics_sessions','SELECT')
        """).fetchone()[0] is False


def test_reapplying_075_is_not_silent_idempotent_migration(v2_db):
    _, env = v2_db
    cmd = [
        "/usr/lib/postgresql/18/bin/psql", "-X", "-v", "ON_ERROR_STOP=1",
        "-d", "empire_analytics_fixture", "-f", str(MIGRATION),
    ]
    run = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=25)
    assert run.returncode != 0
    assert ("ANALYTICS075_V1_BASE_CONSTRAINTS_CHANGED" in run.stderr
            or "ANALYTICS075_V2_ALREADY_PRESENT" in run.stderr)
