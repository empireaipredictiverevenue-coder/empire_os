"""Private consumer PostgreSQL connection custody; disabled until provisioned.

No production credentials, env-variable discovery, SQL provisioning, outbound,
web route mounting, or default activation. One injected DSN may open ONLY a
named, nonprivileged consumer login with an explicit inherited capability.
Checks execute in a transaction before the connection is returned to the
private repository. Identity and sensitive email rows are never logged.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict

DATABASE = "empiredb"
LOGIN = "empire_consumer_optin_login"
WRITER = "empire_consumer_optin_writer"
PURPOSE = "empire_own_brand_homeowner_updates"
TABLES = (
    "empire_consumer_subscriptions",
    "empire_consumer_consent_events",
    "empire_consumer_email_suppressions",
    "empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)

# Do not let caller-owned PG* environment or arbitrary DSNs choose a database,
# superuser, search path, replica, service file, or Unix peer identity.
ALLOW_DSN_OPTIONS = frozenset(("host", "port", "dbname", "user", "password",
                              "sslmode", "sslrootcert"))


def validate_private_dsn(dsn: str) -> dict[str, str]:
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("PRIVATE_DSN_REQUIRED")
    try:
        opts = conninfo_to_dict(dsn)
    except (ValueError, TypeError, psycopg.ProgrammingError) as ex:
        raise ValueError("INVALID_PRIVATE_DSN") from ex
    if set(opts) - ALLOW_DSN_OPTIONS:
        raise ValueError("PRIVATE_DSN_UNEXPECTED_OPTIONS")
    if opts.get("dbname") != DATABASE or opts.get("user") != LOGIN:
        raise ValueError("PRIVATE_DSN_MUST_USE_CONSUMER_LOGIN")
    host = opts.get("host", "")
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("PRIVATE_DSN_LOOPBACK_REQUIRED")
    if opts.get("port", "5432") != "5432":
        raise ValueError("PRIVATE_DSN_CANONICAL_PORT_REQUIRED")
    # Password must be provisioned separately into an operator-reviewed
    # protected secrets file and injected by the private service owner.
    if len(opts.get("password", "")) < 32:
        raise ValueError("PRIVATE_DSN_SECRET_REQUIRED")
    if opts.get("sslmode") not in (None, "require", "verify-full"):
        raise ValueError("PRIVATE_DSN_TLS_POLICY_NOT_APPROVED")
    return opts


@dataclass
class PrivateConsumerConnectionFactory:
    dsn: str = field(repr=False)
    owner_authorized: bool = False
    connect: Callable[..., Any] = field(default=psycopg.connect, repr=False)

    def __post_init__(self) -> None:
        validate_private_dsn(self.dsn)

    def _check_connected(self, conn: Any) -> None:
        """Fail closed on an inherited owner role or surprising grants."""
        who = conn.execute(
            "SELECT session_user,current_user,current_database(),"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if not who or who[:3] != (LOGIN, WRITER, DATABASE) or who[3] != "off":
            raise RuntimeError("CONSUMER_WRITER_CONNECTION_IDENTITY_MISMATCH")
        security = conn.execute(
            "SELECT login.rolcanlogin,login.rolinherit,login.rolsuper,"
            "login.rolbypassrls,login.rolcreatedb,login.rolcreaterole,"
            "login.rolreplication,writer.rolcanlogin,writer.rolinherit,"
            "writer.rolsuper,writer.rolbypassrls,"
            "pg_has_role(%s,%s,'MEMBER'),"
            "pg_has_role(%s,'empiredb_migrator','MEMBER'),"
            "pg_has_role(%s,'empiredb_app','MEMBER') "
            "FROM pg_roles login CROSS JOIN pg_roles writer "
            "WHERE login.rolname=%s AND writer.rolname=%s",
            (LOGIN,WRITER,LOGIN,LOGIN,LOGIN,WRITER),
        ).fetchone()
        expected=(True,False,False,False,False,False,False,
                  False,False,False,False,True,False,False)
        if not security or tuple(security) != expected:
            raise RuntimeError("CONSUMER_WRITER_PRIVILEGE_BOUNDARY_FAILED")
        additional=conn.execute(
            "SELECT count(*) FROM pg_auth_members m "
            "JOIN pg_roles member ON member.oid=m.member "
            "JOIN pg_roles granted ON granted.oid=m.roleid "
            "WHERE member.rolname=%s AND granted.rolname<>%s",
            (LOGIN,WRITER),
        ).fetchone()
        if not additional or additional[0]!=0:
            raise RuntimeError("CONSUMER_LOGIN_UNRELATED_ROLE_MEMBERSHIP")
        # Privileges under SET ROLE are also constrained by FORCE RLS. Reject
        # any membership granting access to the general B2B application.
        table_count=conn.execute(
            "SELECT count(*) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s) "
            "AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity "
            "AND pg_get_userbyid(c.relowner)='empiredb_migrator'",
            (list(TABLES),),
        ).fetchone()
        policies=conn.execute(
            "SELECT count(*) FROM pg_policies "
            "WHERE schemaname='public' AND policyname LIKE %s "
            "AND tablename=ANY(%s)",
            ("consumer_writer_%",list(TABLES)),
        ).fetchone()
        if (not table_count or table_count[0]!=5
            or not policies or policies[0]!=5):
            raise RuntimeError("CONSUMER_SCHEMA_AUTHORITY_INVALID")
        for table in TABLES:
            name="public."+table
            grants=conn.execute(
                "SELECT has_table_privilege(%s,%s,'SELECT'),"
                "has_table_privilege('empiredb_app',%s,'SELECT'),"
                "has_table_privilege('empiredb_readonly',%s,'SELECT')",
                (WRITER,name,name,name),
            ).fetchone()
            if not grants or tuple(grants)!=(True,False,False):
                raise RuntimeError("CONSUMER_SCHEMA_TABLE_ACCESS_INVALID")

    def __call__(self) -> Any:
        if self.owner_authorized is not True:
            raise RuntimeError("PRIVATE_CONSUMER_CONNECTION_NOT_APPROVED")
        conn=None
        try:
            conn=self.connect(
                self.dsn, connect_timeout=5,
                application_name="empire_consumer_optin_private",
            )
            # Transaction-local role selection: never persist a capability
            # across a different request when connections are reused.
            conn.execute("SET LOCAL ROLE " + WRITER)
            conn.execute("SET LOCAL statement_timeout='4000ms'")
            conn.execute("SET LOCAL lock_timeout='1500ms'")
            self._check_connected(conn)
            return conn
        except Exception:
            if conn is not None:
                conn.close()
            raise
