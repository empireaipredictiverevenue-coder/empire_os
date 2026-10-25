"""V4.10 independently bounded EmpireDB source-rights HELD reader acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import os
import shutil
import subprocess

import pytest

from empire_os.predictive_cloud_v410_rights_reader import (
    EmpireDbHeldSourceRightsReader, HeldRightsObservation,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/empiredb/066_predictive_source_rights_inventory_held.sql"
FIXTURE = ROOT / "scripts/rehearse_predictive_cloud_v410_source_rights_20261025.sh"
SOURCE = "a" * 64
TENANT = "00000000-0000-0000-0000-000000000101"


def test_v410_schema_prepared_held_with_restricted_rights_capability():
    src = MIGRATION.read_text()
    assert "PREPARED HELD source-rights evidence" in src
    assert "V4_066_RESTRICTED_OWNER_REQUIRED" in src
    assert "V4_066_NOLOGIN_READER_CAPABILITY_REQUIRED" in src
    assert "source_review_state IN ('PENDING','CANDIDATE_REVIEWED')" in src
    assert "GRANT EXECUTE ON FUNCTION public.read_empire_predictive_source_rights_held" in src
    assert "TO empire_predictive_rights_reader" in src
    assert "session_user <> 'empire_predictive_rights_login'" in src
    assert "ENABLE ROW LEVEL SECURITY" in src
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "source_admission_authorized" in src
    assert "false,false,'none'::text" in src
    assert "V4_066_APPEND_ONLY_SOURCE_HISTORY" in src
    assert "ON DELETE RESTRICT" in src
    assert "CREATE ROLE empire_predictive_rights_login" not in src
    assert "CANDIDATE_REVIEWED' THEN 'APPROVED'" not in src


@pytest.mark.parametrize("tenant,source", [
    ("not-a-uuid", SOURCE),
    ("00000000-0000-0000-0000-000000000000", SOURCE),
    ('AAAAAAAA-0000-0000-0000-000000000101', SOURCE),
    (TENANT, "email@example.com"),
    (TENANT, SOURCE.upper()),
    (TENANT, "b" * 63),
])
def test_v410_invalid_untrusted_tenant_or_source_fails_without_sql(tenant, source):
    called = []
    def forbidden_connect(_dsn):
        called.append(1)
        raise AssertionError("should not connect")
    reader = EmpireDbHeldSourceRightsReader("test", connect_factory=forbidden_connect)
    assert reader(tenant, source) is None
    assert not called


def test_v410_missing_connection_config_fails_closed():
    with pytest.raises(ValueError, match="owner-provided"):
        EmpireDbHeldSourceRightsReader("")


class FakeCursor:
    def __init__(self, identity, rows):
        self._data = iter([identity, *rows])
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return next(self._data, None)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_inst = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_inst


def fake_reader(row, identity=("empire_predictive_rights_login",), extras=()):
    cursor = FakeCursor(identity, [row, *extras])
    reader = EmpireDbHeldSourceRightsReader(
        "owned",
        connect_factory=lambda _: FakeConnection(cursor),
    )
    return reader, cursor


def _row(
    decision="CANDIDATE_REVIEW_HELD",
    tenant=TENANT,
    source=SOURCE,
    purpose="PRIVATE_PREDICTIVE_RESEARCH_ONLY",
    revoked=False,
    verified=False,
    admitted=False,
    authority="none",
):
    return (decision, tenant, source, purpose, revoked, verified, admitted, authority)


def test_v410_valid_candidate_observation_is_never_admission():
    reader, cursor = fake_reader(_row())
    result = reader(TENANT, SOURCE)
    assert isinstance(result, HeldRightsObservation)
    assert result.decision == "CANDIDATE_REVIEW_HELD"
    assert result.real_rights_independently_verified is False
    assert result.source_admission_authorized is False
    assert result.execution_authority == "none"
    assert cursor.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert cursor.calls[1][0] == "SET LOCAL statement_timeout = '3000ms'"
    assert cursor.calls[2][0] == "SELECT session_user"
    assert cursor.calls[3][1] == (TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY")


@pytest.mark.parametrize("row,identity", [
    (_row(), ("untrusted_role",)),
    (_row(tenant="00000000-0000-0000-0000-000000000102"), ("empire_predictive_rights_login",)),
    (_row(source="b" * 64), ("empire_predictive_rights_login",)),
    (_row(purpose="MARKETING_CONTACT"), ("empire_predictive_rights_login",)),
    (_row(verified=True), ("empire_predictive_rights_login",)),
    (_row(admitted=True), ("empire_predictive_rights_login",)),
    (_row(authority="purchase"), ("empire_predictive_rights_login",)),
    (_row(decision="ADMITTED"), ("empire_predictive_rights_login",)),
    (_row(decision="REVOKED_HELD", revoked=False), ("empire_predictive_rights_login",)),
    (_row(decision="PENDING_HELD", revoked=True), ("empire_predictive_rights_login",)),
    (_row(revoked=1), ("empire_predictive_rights_login",)),
    (_row()[:7], ("empire_predictive_rights_login",)),
    (None, ("empire_predictive_rights_login",)),
])
def test_v410_ambiguous_forged_or_overprivileged_response_denied(row, identity):
    reader, _ = fake_reader(row, identity)
    assert reader(TENANT, SOURCE) is None


def test_v410_duplicate_sql_rows_refused():
    reader, _ = fake_reader(_row(), extras=(_row(),))
    assert reader(TENANT, SOURCE) is None


def test_v410_postgresql_fixture_fails_closed_on_default_port():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432")
    process = subprocess.run(
        ["bash", str(FIXTURE)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=5,
    )
    assert process.returncode != 0
    assert "V410_ORIGINAL_EMPIREDB_HELD_RIGHTS_READ_PASS" not in process.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL unavailable")
def test_v410_real_pg18_restricted_source_reader_and_terminal_revocation():
    result = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(FIXTURE)],
        cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-4000:]
    receipts = [json.loads(line) for line in result.stdout.splitlines()
                if line.startswith("{")]
    assert len(receipts) == 1
    data = receipts[0]
    assert data["status"] == "V410_ORIGINAL_EMPIREDB_HELD_RIGHTS_READ_PASS"
    for name in (
        "original_empiredb_migrator_no_login",
        "isolated_pg18_verified",
        "restricted_real_scram_login_verified",
        "tenant_and_source_scope_enforced",
        "candidate_still_held",
        "revocation_terminal",
        "direct_table_read_denied",
        "untrusted_function_execute_denied",
        "append_only_guards_verified",
        "expired_candidate_blocked",
    ):
        assert data[name] is True
    for name in (
        "real_licenses_authenticated", "source_authorized",
        "live_empiredb_migrations_applied", "redis_published", "money_moved",
    ):
        assert data[name] is False
    assert "Dropping cluster 18/regress" in result.stdout + result.stderr
