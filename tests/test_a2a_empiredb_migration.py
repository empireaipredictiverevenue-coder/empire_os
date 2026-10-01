from pathlib import Path

SQL = Path("migrations/empiredb/026_a2a_commercial_intent_authority.sql").read_text()


def test_a2a_roles_are_narrow_no_login_capabilities():
    assert "CREATE ROLE empire_a2a_identity_nonce_writer NOLOGIN" in SQL
    assert "CREATE ROLE empire_a2a_intent_writer NOLOGIN" in SQL
    assert "GRANT USAGE ON SCHEMA public TO empire_a2a_identity_nonce_writer, empire_a2a_intent_writer" in SQL


def test_nonce_rpc_is_security_definer_and_only_granted_to_identity_role():
    assert "FUNCTION public.consume_a2a_identity_nonce" in SQL
    assert "SECURITY DEFINER SET search_path = pg_catalog" in SQL
    assert "TO empire_a2a_identity_nonce_writer;" in SQL
    assert "ON CONFLICT DO NOTHING" in SQL


def test_intent_rpc_is_non_binding_and_fail_closed():
    assert "status text NOT NULL DEFAULT 'pending_approval' CHECK (status = 'pending_approval')" in SQL
    assert "execution_authority text NOT NULL DEFAULT 'none' CHECK (execution_authority = 'none')" in SQL
    assert "payment_authority boolean NOT NULL DEFAULT false CHECK (NOT payment_authority)" in SQL
    assert "allocation_authority boolean NOT NULL DEFAULT false CHECK (NOT allocation_authority)" in SQL
    assert "TO empire_a2a_intent_writer;" in SQL
    assert "a2a_idempotency_conflict" in SQL


def test_generic_app_and_public_are_revoked():
    assert "FROM PUBLIC, empiredb_app" in SQL
    assert "GRANT empiredb_app" not in SQL
