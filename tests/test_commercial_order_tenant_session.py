"""Tenant-only canonical order review authorization; offline no credentials."""
from __future__ import annotations

import pytest

from empire_os.commercial_order_tenant_session import (
    REQUIRED_RELATIONS, READ_ONLY_SQL, READER_PROOF_SQL,
    TenantOrderSessionHeld, prove_exact_tenant_readonly_session,
)
from test_authenticated_commercial_outcome_intelligence import TENANT, OTHER_ORDER


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Session:
    def __init__(self, **overrides):
        self.initial = (
            "empire_customer_tenant_login", "empire_customer_tenant_login",
            True, False, False, False, False, False, "empiredb", "on",
        )
        self.tenant_binding = overrides.get("tenant_binding", TENANT)
        changes = overrides.get('initial_overrides', {})
        self.initial = tuple(changes.get(i, v) for i, v in enumerate(self.initial))
        self.rows = []
        self.role = False
        self.select_permissions = dict(overrides.get("select_permissions", {}))
        self.rls = dict(overrides.get("rls", {}))

    def execute(self, sql, params=()):
        self.rows.append((sql, params))
        if sql == READ_ONLY_SQL:
            return Cursor(self.initial)
        if sql == "SET LOCAL ROLE empiredb_tenant_reader":
            self.role = True
            return Cursor(None)
        if sql == READER_PROOF_SQL:
            assert self.role is True
            relation = params[0]
            assert params == (relation, relation)
            return Cursor((
                self.initial[0], "empiredb_tenant_reader",
                self.tenant_binding, "on",
                self.select_permissions.get(relation, True),
                self.rls.get(relation, True),
            ))
        raise AssertionError("unapproved SQL statement")


class Snapshot:
    state = "active"

    def __init__(self, session):
        self._session = session


def _review(**overrides):
    session = Session(**overrides)
    proof = prove_exact_tenant_readonly_session(Snapshot(session), tenant_id=TENANT)
    return proof, session


def test_valid_tenant_login_before_any_commercial_order_query():
    proof, session = _review()
    assert proof["status"] == "TENANT_SCOPED_READONLY_RLS_SESSION_VERIFIED"
    assert proof["verified_relation_count"] == len(REQUIRED_RELATIONS) == 8
    assert session.rows[0][0] == READ_ONLY_SQL
    assert session.rows[1][0] == "SET LOCAL ROLE empiredb_tenant_reader"
    assert all(sql == READER_PROOF_SQL for sql, _ in session.rows[2:])
    assert proof["database_writes"] is False
    assert TENANT not in str(proof)


@pytest.mark.parametrize("index,value", [
    (0, "postgres"),
    (0, "empiredb_app"),
    (1, "empiredb_tenant_reader"),
    (2, False),
    (3, True),
    (4, True),
    (5, True),
    (6, True),
    (7, True),
    (8, "unrelated"),
    (9, "off"),
])
def test_rejects_unauthorized_role_tenant_or_write_context_before_setrole(index, value):
    session = Session(initial_overrides={index: value})
    with pytest.raises(TenantOrderSessionHeld) as exc:
        prove_exact_tenant_readonly_session(Snapshot(session), tenant_id=TENANT)
    assert str(exc.value) == "TENANT_SESSION_IDENTITY_OR_ROLE_HOLD"
    assert len(session.rows) == 1
    assert "tenant" not in str(exc.value).lower() or "HOLD" in str(exc.value)


@pytest.mark.parametrize("relation", REQUIRED_RELATIONS)
def test_missing_any_exact_relation_grant_denies_every_order_read(relation):
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_READER_ACL_OR_RLS_HOLD"):
        _review(select_permissions={relation: False})


def test_role_level_rls_bypass_denied_even_if_grants_present():
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_READER_ACL_OR_RLS_HOLD"):
        _review(rls={"public.commercial_outcomes": False})


def test_absent_snapshot_cannot_access_unsafe_connection():
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_SESSION_PROOF_UNAVAILABLE"):
        prove_exact_tenant_readonly_session(object(), tenant_id=TENANT)


def test_fake_tenant_uuid_denied_without_source_read():
    s = Session()
    with pytest.raises(TenantOrderSessionHeld, match="UNAUTHORIZED_TENANT_SCOPE"):
        prove_exact_tenant_readonly_session(Snapshot(s), tenant_id="private@example.invalid")
    assert s.rows == []


def test_readonly_metadata_fails_closed_without_echoing_sql_or_private_data():
    class Broken:
        def execute(self, *_args):
            raise RuntimeError("private@example.invalid and admin password")
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_SESSION_PROOF_UNAVAILABLE") as exc:
        prove_exact_tenant_readonly_session(Snapshot(Broken()), tenant_id=TENANT)
    assert "private@" not in str(exc.value)
    assert TENANT not in str(exc.value)


def test_session_tenant_binding_mismatch_is_denied_after_setrole():
    s = Session(tenant_binding=OTHER_ORDER)
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_READER_ACL_OR_RLS_HOLD"):
        prove_exact_tenant_readonly_session(Snapshot(s), tenant_id=TENANT)
    assert s.rows[1][0] == "SET LOCAL ROLE empiredb_tenant_reader"
    assert not any("fulfilment_orders" in str(x) for x in s.rows[:2])


def test_pg_sql_ascii_bytes_are_decoded_only_for_short_metadata():
    class Encoded(Session):
        def execute(self, sql, params=()):
            original = super().execute(sql, params)
            if sql == "SET LOCAL ROLE empiredb_tenant_reader":
                return original
            return Cursor(tuple(
                x.encode("ascii") if isinstance(x, str) else x
                for x in original.fetchone()
            ))
    proof = prove_exact_tenant_readonly_session(Snapshot(Encoded()), tenant_id=TENANT)
    assert proof["tenant_identity_resolved_from_original_db_session"] is True


def test_malformed_database_text_is_held_without_raw_bytes():
    class BadBytes(Session):
        def execute(self, sql, params=()):
            if sql == READ_ONLY_SQL:
                row = list(super().execute(sql, params).fetchone())
                row[0] = bytes([255, 254])
                return Cursor(tuple(row))
            return super().execute(sql, params)
    with pytest.raises(TenantOrderSessionHeld, match="TENANT_SESSION_PROOF_UNAVAILABLE"):
        prove_exact_tenant_readonly_session(Snapshot(BadBytes()), tenant_id=TENANT)
