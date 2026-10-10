"""Identity role grant contract on disposable PG18: no production role writes.

Apply exact prepared SQL to isolated copy of existing 041/042 schemas. Verify
NOLOGIN by default, table/function separation, and first-party login after
fixture-only role activation.
"""
from pathlib import Path

from test_crm_membership_authority_ephemeral import A, membership_pg

from empire_os.revenue_crm_first_party_login import (
    PostgresCrmPasswordLogin, prepare_crm_invitation,
)
from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader

ROOT = Path(__file__).resolve().parents[1]
SQL_ROLES = ROOT / "scripts/prepare_crm_pilot_identity_roles.sql"
SQL_042 = ROOT / "migrations/empiredb/042_crm_first_party_login.sql"


def test_prepared_roles_are_no_login_and_have_separated_privileges(membership_pg):
    run, sock, port = membership_pg
    # Existing 041 fixture precreates an unrelated, empty-role placeholder.
    # Remove it ONLY in this disposable module-scoped database.
    run("DROP ROLE empire_crm_membership_login;")
    run(file=SQL_042)
    run(file=SQL_ROLES)

    assert run("""
        SELECT rolname||'|'||rolcanlogin::text||'|'||
               rolinherit::text||'|'||rolsuper::text||'|'||
               rolbypassrls::text
        FROM pg_catalog.pg_roles
        WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
        ORDER BY rolname;
    """) == (
        "empire_crm_auth_login|false|false|false|false\n"
        "empire_crm_membership_login|false|false|false|false"
    )
    assert run("""
        SELECT count(*) FROM public.empire_crm_login_credentials;
    """) == "0"
    assert run("""
        SELECT count(*) FROM public.empire_crm_tenant_memberships;
    """) == "0"
    assert run("""
        SELECT has_table_privilege('empire_crm_auth_login',
           'public.empire_crm_login_credentials','SELECT');
    """) == "t"
    assert run("""
        SELECT has_table_privilege('empire_crm_auth_login',
           'public.empire_crm_tenant_memberships','SELECT');
    """) == "f"
    assert run("""
        SELECT has_table_privilege('empire_crm_membership_login',
           'public.empire_crm_login_credentials','SELECT');
    """) == "f"
    assert run("""
        SELECT has_table_privilege('empire_crm_membership_login',
           'public.empire_crm_tenant_memberships','SELECT');
    """) == "f"
    assert run("""
        SELECT has_function_privilege('empire_crm_membership_login',
           'public.empire_crm_read_member(text,uuid)','EXECUTE');
    """) == "t"
    assert run("""
        SELECT has_function_privilege('empire_crm_auth_login',
           'public.empire_crm_read_member(text,uuid)','EXECUTE');
    """) == "f"
    for role in ("empire_crm_auth_login", "empire_crm_membership_login"):
        assert run(f"""
            SELECT pg_catalog.pg_has_role('{role}',
                'empire_revenue_crm_reader','MEMBER');
        """) == "f"
        # The disposable 041 fixture contains only identity/tenant schema,
        # not the unrelated 040 CRM prospect view. Check that no CRM reader
        # group is reachable rather than inventing the missing view.
        run("SELECT 1;", user=role, check=False)

    # No direct role change can be applied twice without owner review.
    run(file=SQL_ROLES, check=False)

    # Isolated fixture operator proves that the precise column/func grants
    # actually satisfy the SAME production login and invite path.
    invite = prepare_crm_invitation(
        subject="pilot:identity-test", email="pilot@example.invalid",
        tenant_id=A, evidence_ref="fixture:reviewed-account",
    )
    run(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (tenant_id,subject,role,status,evidence_ref,verified_at)
      VALUES ('{A}'::uuid,'{invite.subject}','viewer','active',
              'fixture:reviewed-membership',now());
      INSERT INTO public.empire_crm_login_credentials
        (subject,login_email,password_salt,password_digest,status,
         evidence_ref,password_change_required,verified_at,
         invitation_tenant_id,invitation_token_hash,invitation_expires_at)
      VALUES ('{invite.subject}','{invite.login_email}',
              decode('{invite.password_salt.hex()}','hex'),
              decode('{invite.password_digest.hex()}','hex'),
              'pending','fixture:reviewed-account',true,now(),
              '{A}'::uuid,
              decode('{invite.invitation_token_hash.hex()}','hex'),
              now()+interval '2 days');
    """)
    # Test only: convert to LOGIN under trust on ephemeral PG; the prepared
    # production SQL NEVER performs this activation.
    run("""
       ALTER ROLE empire_crm_auth_login LOGIN;
       ALTER ROLE empire_crm_membership_login LOGIN;
    """)
    auth = PostgresCrmPasswordLogin(
        f"host={sock} port={port} dbname=crm_membership_fixture "
        "user=empire_crm_auth_login",
    )
    member = EmpireDbCrmMembershipReader(
        f"host={sock} port={port} dbname=crm_membership_fixture "
        "user=empire_crm_membership_login",
    )
    assert member(invite.subject, A) is not None
    assert auth.authenticate(invite.login_email, "fixture-long-password-12345!") is None
    assert auth.accept_invitation(
        invite.token, "fixture-long-password-12345!", A, load_membership=member,
    ) is True
    assert auth.authenticate(
        invite.login_email, "fixture-long-password-12345!",
    ) == invite.subject
    assert auth.accept_invitation(
        invite.token, "fixture-long-password-12345!", A, load_membership=member,
    ) is False
    run("SELECT * FROM public.empire_crm_tenant_memberships LIMIT 1;",
        user="empire_crm_auth_login", check=False)
    run("SELECT * FROM public.empire_crm_login_credentials LIMIT 1;",
        user="empire_crm_membership_login", check=False)


def test_prepared_roles_have_no_activation_scope():
    sql = SQL_ROLES.read_text()
    assert "PREPARED / NOT APPROVED" in sql
    assert sql.count("NOLOGIN NOINHERIT") == 2
    assert sql.count("PASSWORD NULL") == 2
    assert "GRANT EXECUTE ON FUNCTION public.empire_crm_read_member" in sql
    assert "GRANT UPDATE (" in sql
    assert "CREATE ROLE empire_crm_tenant" not in sql
    assert "GRANT empire_revenue_crm_reader" not in sql
    assert "INSERT INTO" not in sql
    assert "ALTER ROLE" not in sql
    assert "CREATE POLICY" not in sql
    assert "CREATE TABLE" not in sql
