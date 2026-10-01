from scripts.provision_zero_paid_revenue_runtime import ROLES, _role_provision_sql


def test_role_sql_uses_narrow_login_roles_and_capability_membership():
    passwords = {login: "safe_test_password_123" for login, _ in ROLES}
    text = _role_provision_sql(passwords)
    for login, capability in ROLES:
        assert f"CREATE ROLE {login} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE" in text
        assert f"ALTER ROLE {login} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE" in text
        assert f"GRANT CONNECT ON DATABASE empiredb TO {login};" in text
        assert f"GRANT {capability} TO {login};" in text
        assert f"REVOKE ALL ON SCHEMA public FROM {login};" in text
    privileged = text.replace("NOCREATEROLE", "").replace("NOSUPERUSER", "")
    assert " CREATEROLE" not in privileged
    assert " SUPERUSER" not in privileged


def test_role_sql_is_single_transaction():
    passwords = {login: "safe_test_password_123" for login, _ in ROLES}
    text = _role_provision_sql(passwords)
    assert text.startswith("BEGIN;\n")
    assert text.endswith("COMMIT;\n")
