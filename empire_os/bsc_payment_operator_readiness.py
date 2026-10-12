"""Read-only mainnet BSC financial-operator *identity* readiness.

This inspects the existing canonical EmpireDB/PostgreSQL 18 catalog without
creating logins, modifying HBA, granting roles, issuing credentials, creating
orders, or authorizing escrow/funds. No Supabase or third-party service.

The two financial identities MUST have separate LOGIN roles and may SET only
their corresponding existing NOLOGIN permission role. Merely seeing a member
count of 1 is never sufficient to establish safe operator provisioning.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

APP = "empiredb_app_login"
DB = "empiredb"
EXPECTED = {
    "empire_payment_approver": "empire_payment_approver_login",
    "empire_escrow_verifier": "empire_escrow_verifier_login",
}
TARGET_ROLES = tuple(EXPECTED)
LOGIN_ROLES = tuple(EXPECTED.values())
MANDATORY_FUNCTIONS = {
    "empire_payment_approver": (
        "public.get_bsc_payment_request_review(uuid)",
        "public.approve_bsc_payment_request(uuid,text,text)",
        "public.cancel_bsc_payment_request(uuid,text,text)",
    ),
    "empire_escrow_verifier": (
        "public.get_bsc_escrow_request_review(uuid)",
        "public.record_bsc_escrow_creation(uuid,jsonb)",
        "public.record_bsc_escrow_lifecycle(uuid,text,jsonb)",
    ),
}
ROLE_ATTRIBUTES = (
    "rolcanlogin", "rolinherit", "rolsuper", "rolcreatedb",
    "rolcreaterole", "rolreplication", "rolbypassrls",
)
PERMISSION_ROLE_FLAGS = (False,) * 7
LOGIN_FLAGS = (True, False, False, False, False, False, False)


def effective_scram_rule(rows: Iterable[dict[str, Any]], login: str) -> bool:
    """Prove first matching local HBA rule has exact DB, login and SCRAM.

    Do not mistake a later rule for effective authentication when a generic
    peer/trust/ident rule earlier has already matched.
    """
    if login not in LOGIN_ROLES:
        return False
    parsed = list(rows)
    if not parsed or any(not isinstance(r, dict) or r.get("error") for r in parsed):
        return False
    def rank(r: dict[str, Any]) -> int:
        raw = r.get("rule_number")
        if type(raw) is not int or raw < 0:
            return 999999999
        return raw
    for row in sorted(parsed, key=rank):
        if row.get("type") != "local":
            continue
        dbs = row.get("database")
        users = row.get("user_name")
        if not isinstance(dbs, list) or not isinstance(users, list):
            return False
        # Includes can be complex; reject any unrecognized potential shadow.
        db_matches = DB in dbs or "all" in dbs or "sameuser" in dbs
        user_matches = login in users or "all" in users or "sameuser" in users
        user_matches = user_matches or any(
            isinstance(u, str) and (u.startswith("+") or u.startswith("@"))
            for u in users
        )
        if not db_matches or not user_matches:
            continue
        return (
            dbs == [DB]
            and users == [login]
            and row.get("auth_method") == "scram-sha-256"
            and row.get("error") is None
        )
    return False


def classify(
    *,
    roles: Mapping[str, tuple],
    memberships: Iterable[tuple[str, str, bool, bool, bool]],
    hba: Iterable[dict[str, Any]],
    function_bits: Mapping[tuple[str, str], bool],
    application_bits: Mapping[str, bool],
    canonical_db: bool = True,
    existing_private_credential_vault: bool = False,
    database_privileges: Mapping[str, tuple[bool, bool, bool]] | None = None,
) -> dict[str, Any]:
    """Pure fail-closed assessment from trusted PostgreSQL read-only catalog."""
    hba = list(hba)
    memberships = list(memberships)
    groups_ok = all(roles.get(name) == PERMISSION_ROLE_FLAGS for name in TARGET_ROLES)
    app_role_safe = roles.get(APP) == (True, True, False, False, False, False, False)
    login_exists = [name for name in LOGIN_ROLES if name in roles]
    login_complete = len(login_exists) == 2
    login_safe = login_complete and all(roles[name] == LOGIN_FLAGS for name in LOGIN_ROLES)
    function_rights_ok = all(
        function_bits.get((role, signature)) is True
        for role, signatures in MANDATORY_FUNCTIONS.items()
        for signature in signatures
    )
    app_separate = all(application_bits.get(sig) is False for sig in (
        "public.approve_bsc_payment_request(uuid,text,text)",
        "public.record_bsc_escrow_creation(uuid,jsonb)",
        "public.record_bsc_escrow_lifecycle(uuid,text,jsonb)",
    ))
    members = list(memberships)
    member_types_ok = all(
        isinstance(x, tuple) and len(x) == 5
        and isinstance(x[0], str) and isinstance(x[1], str)
        and all(type(z) is bool for z in x[2:])
        for x in members
    )
    allowed = {
        (group, login, False, True, False)
        for group, login in EXPECTED.items()
    }
    membership_exact = member_types_ok and len(members) == 2 and set(members) == allowed
    no_roles_yet = not members
    hba_ready = all(effective_scram_rule(hba, role) for role in LOGIN_ROLES)
    parsed_hba_ok = bool(hba) and all(r.get("error") is None for r in hba)
    dbpriv = database_privileges or {}
    dbpriv_valid = all(
        login in dbpriv and isinstance(dbpriv[login], tuple)
        and len(dbpriv[login]) == 3
        and all(type(x) is bool for x in dbpriv[login])
        for login in login_exists
    )
    unsafe_dbpriv = any(
        dbpriv.get(login, (False, False, False))[1:] != (False, False)
        for login in login_exists
    )
    connect_count = sum(dbpriv.get(login, (False, False, False))[0] is True for login in login_exists)
    base = canonical_db and groups_ok and app_role_safe and function_rights_ok and app_separate and parsed_hba_ok
    if not base:
        status = "BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT"
    elif login_exists and not login_safe:
        status = "BLOCKED_PARTIAL_OR_UNSAFE_OPERATOR_LOGINS"
    elif login_exists and not dbpriv_valid:
        status = "BLOCKED_DATABASE_PRIVILEGE_CATALOG_UNAVAILABLE"
    elif unsafe_dbpriv:
        status = "BLOCKED_UNSAFE_DATABASE_CREATE_OR_TEMP_GRANT"
    elif members and not membership_exact:
        status = "BLOCKED_UNEXPECTED_FINANCIAL_ROLE_MEMBERSHIP"
    elif existing_private_credential_vault and not login_complete:
        status = "BLOCKED_PREEXISTING_OPERATOR_CREDENTIAL_VAULT"
    elif not login_exists and no_roles_yet and not hba_ready:
        status = "PREPARE_EXACT_TWO_LOCAL_SCRAM_HBA_RULES"
    elif not login_exists and no_roles_yet and hba_ready:
        status = "READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING"
    elif login_safe and membership_exact and hba_ready and connect_count == 0:
        status = "OPERATOR_IDENTITIES_REQUIRE_EXACT_TWO_DATABASE_CONNECT_GRANTS"
    elif login_safe and membership_exact and hba_ready and connect_count == 1:
        status = "BLOCKED_PARTIAL_DATABASE_CONNECT_GRANTS"
    elif login_safe and membership_exact and hba_ready and connect_count == 2:
        status = "OPERATOR_IDENTITIES_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"
    else:
        status = "BLOCKED_UNSAFE_OPERATOR_DEPLOYMENT_SEQUENCE"
    return {
        "schema_version": "empire.bsc-two-financial-operator-readiness.v1",
        "mode": "READ_ONLY",
        "status": status,
        "canonical_sov_db": bool(canonical_db),
        "exact_existing_nologin_permission_roles_safe": groups_ok,
        "app_login_not_financial_operator": app_separate and app_role_safe,
        "six_existing_role_rpc_grants_verified": function_rights_ok,
        "pg_hba_rules_parse_cleanly": parsed_hba_ok,
        "two_exact_local_scram_rules_effective": hba_ready,
        "dedicated_login_count": len(login_exists),
        "dedicated_login_attributes_safe": bool(login_safe),
        "exact_noninherited_set_role_memberships": bool(membership_exact),
        "no_financial_role_memberships": no_roles_yet,
        "operator_db_connect_grant_count": connect_count,
        "no_operator_database_create_or_temp_privileges": dbpriv_valid and not unsafe_dbpriv,
        "private_operator_vault_already_present": existing_private_credential_vault,
        "credential_values_read_or_printed": False,
        "financial_operator_authenticated": False,
        "financial_authority_activated": False,
        "hba_modified": False,
        "roles_created": 0,
        "memberships_granted": 0,
        "database_mutations": 0,
        "payments_collected": False,
        "funds_moved": False,
        "existing_four_product_founder_pricing_approval_retained": True,
    }


def inspect_catalog(conn_factory: Callable, *, vault_exists: bool = False) -> dict[str, Any]:
    """Query only pg_catalog; no business-table reads and no writes."""
    with conn_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '4000ms'")
            cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
            db, user, recovery = cur.fetchone()
            if user != "postgres":
                raise RuntimeError("postgres catalog-operator identity required")
            cur.execute("""
               SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
                      rolcreaterole,rolreplication,rolbypassrls
               FROM pg_catalog.pg_roles
               WHERE rolname IN (%s,%s,%s,%s,%s)
            """, (*TARGET_ROLES,*LOGIN_ROLES,APP))
            roles = {row[0]: tuple(row[1:]) for row in cur.fetchall()}
            cur.execute("""
                SELECT g.rolname,m.rolname,a.inherit_option,a.set_option,a.admin_option
                FROM pg_catalog.pg_auth_members a
                JOIN pg_catalog.pg_roles g ON g.oid=a.roleid
                JOIN pg_catalog.pg_roles m ON m.oid=a.member
                WHERE g.rolname IN (%s,%s) OR m.rolname IN (%s,%s)
                ORDER BY g.rolname,m.rolname
            """, (*TARGET_ROLES,*LOGIN_ROLES))
            members = cur.fetchall()
            cur.execute("""
                SELECT rule_number,type,database,user_name,auth_method,error
                FROM pg_catalog.pg_hba_file_rules
            """)
            names = ("rule_number","type","database","user_name","auth_method","error")
            hba = [dict(zip(names,row)) for row in cur.fetchall()]
            sigs = tuple(s for values in MANDATORY_FUNCTIONS.values() for s in values)
            query_roles = {}
            for role, signatures in MANDATORY_FUNCTIONS.items():
                for signature in signatures:
                    cur.execute("SELECT to_regprocedure(%s) IS NOT NULL,"
                                "has_function_privilege(%s,%s,'EXECUTE')",
                                (signature,role,signature))
                    exists, permitted = cur.fetchone()
                    query_roles[(role,signature)] = bool(exists and permitted)
            dbpriv = {}
            for login in LOGIN_ROLES:
                if login in roles:
                    cur.execute("""
                        SELECT has_database_privilege(%s,%s,'CONNECT'),
                               has_database_privilege(%s,%s,'CREATE'),
                               has_database_privilege(%s,%s,'TEMP')
                    """, (login, DB, login, DB, login, DB))
                    dbpriv[login] = tuple(cur.fetchone())
            app_bits = {}
            for signature in (
                "public.approve_bsc_payment_request(uuid,text,text)",
                "public.record_bsc_escrow_creation(uuid,jsonb)",
                "public.record_bsc_escrow_lifecycle(uuid,text,jsonb)",
            ):
                cur.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                            (APP, signature))
                app_bits[signature] = bool(cur.fetchone()[0])
        conn.rollback()
    return classify(
        roles=roles, memberships=members, hba=hba,
        function_bits=query_roles, application_bits=app_bits,
        canonical_db=db==DB and not recovery,
        existing_private_credential_vault=vault_exists,
        database_privileges=dbpriv,
    )
