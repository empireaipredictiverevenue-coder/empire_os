#!/usr/bin/env python3
"""Read-only, counts-only verification of original founder email DB visibility.

Never a send clearance, intent approval, suppression write, or replay of Gmail.
This program emits no recipient address, DSN, role credentials or contact data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from empire_os.founder_acquisition_autopilot import load_ledger

ROOT = Path("/srv/empire_os")
SENDER_ENV = ROOT / "runtime/secrets/outbound.env"
TABLES = ("public.outbound_suppressions", "public.outbound_intents")
SQL_POLICIES = """
SELECT polcmd, polpermissive, pg_get_expr(polqual, polrelid), polroles
FROM pg_catalog.pg_policy WHERE polrelid=%s::regclass
"""
SQL_TABLE = """
SELECT c.relrowsecurity,c.relforcerowsecurity,
       row_security_active(c.oid::regclass)
FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(%s)
"""


def policy_all_rows_visible(
    rls_enabled: bool, rls_active: bool,
    policies: list[tuple[Any, ...]], current_role_oid: int,
) -> bool:
    """Conservatively prove unrestricted SELECT visibility, never by count."""
    if type(rls_enabled) is not bool or type(rls_active) is not bool:
        return False
    if not rls_enabled:
        return not rls_active
    if not rls_active:
        return False
    unrestricted_permissive = False
    for cmd, permissive, expression, roles in policies:
        if cmd not in ("r", "*"):
            continue
        if not isinstance(roles, (list, tuple)):
            return False
        # A restrictive policy granted through another group role could
        # filter rows: reject any nontrivial one conservatively.
        unconditional = expression is None or bool(re.fullmatch(
            r"\(*\s*true\s*\)*", str(expression).strip(), flags=re.I
        ))
        if not permissive and not unconditional:
            return False
        if permissive and unconditional and (
            0 in roles or current_role_oid in roles
        ):
            unrestricted_permissive = True
    return unrestricted_permissive


def load_sender_dsn(path: Path) -> str:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("PRIVILEGED_SENDER_ENV_REQUIRED")
    key = "EMPIRE_OUTBOUND_SENDER_DSN="
    candidates = []
    for item in path.read_text(encoding="utf-8").splitlines():
        line = item.strip().removeprefix("export ").strip()
        if line.startswith(key):
            candidates.append(line[len(key):].strip().strip('"\''))
    if len(candidates) != 1 or not candidates[0]:
        raise ValueError("EXACT_SENDER_DSN_MISSING")
    return candidates[0]


def run(root: Path = ROOT, env: Path = SENDER_ENV, connect=None) -> dict[str, Any]:
    output: dict[str, Any] = {
        "schema_version": "empire.founder_canonical_email_visibility.v1",
        "status": "HELD_CANONICAL_VISIBILITY_UNVERIFIED",
        "recipient_count": 9,
        "database_login_verified": False,
        "full_rls_visibility_verified": False,
        "historical_email_clearance": "NOT_VERIFIED",
        "canonical_intent_authority": "NOT_VERIFIED",
        "prior_gmail_sends": "EXISTING_ONLY",
        "new_send_authorized": False,
        "database_writes": False,
        "outbound_sent": False,
    }
    try:
        ledger = load_ledger(root)
        anchors = ledger["anchors"]
        if len(anchors) != 9:
            raise ValueError("IMMUTABLE_SENT_UNIVERSE_UNVERIFIED")
        dsn = load_sender_dsn(env)
        if connect is None:
            import psycopg
            connect = psycopg.connect
        with connect(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL ROLE empire_outbound_sender")
                cursor.execute("SET LOCAL statement_timeout='3000ms'")
                cursor.execute("""
                    SELECT current_user,
                           current_setting('transaction_read_only'),
                           oid, rolsuper, rolbypassrls
                    FROM pg_catalog.pg_roles
                    WHERE rolname=current_user
                """)
                identity = cursor.fetchone()
                if (not identity or len(identity) != 5
                    or identity[0] != "empire_outbound_sender"
                    or identity[1] != "on"
                    or identity[3] is not False
                    or identity[4] is not False):
                    raise ValueError("SENDER_ROLE_AUTHORITY_UNVERIFIED")
                oid = identity[2]
                output["database_login_verified"] = True
                for table in TABLES:
                    cursor.execute(
                        "SELECT pg_catalog.has_table_privilege(current_user,%s,'SELECT')",
                        (table,),
                    )
                    if cursor.fetchone() != (True,):
                        raise ValueError("TABLE_SELECT_PERMISSION_UNVERIFIED")
                    cursor.execute(SQL_TABLE, (table,))
                    record = cursor.fetchone()
                    if not record or len(record) != 3:
                        raise ValueError("CANONICAL_TABLE_MISSING")
                    cursor.execute(SQL_POLICIES, (table,))
                    policies = cursor.fetchall()
                    if not policy_all_rows_visible(
                        record[0],record[2],policies,oid
                    ):
                        raise ValueError("CANONICAL_RLS_FULL_VIEW_NOT_PROVEN")
                output["full_rls_visibility_verified"] = True
                checked=[]
                for company,email,_sent_id in anchors:
                    address=email.strip().casefold()
                    domain=address.rsplit("@",1)[-1]
                    cursor.execute("""
                        SELECT count(*) FROM public.outbound_suppressions
                        WHERE lower(btrim(normalized_contact)) IN (%s,%s,%s)
                    """, (address,domain,"@"+domain))
                    suppressed=cursor.fetchone()
                    cursor.execute("""
                        SELECT count(*) FROM public.outbound_intents
                        WHERE channel='email'
                          AND lower(btrim(normalized_recipient))=%s
                    """, (address,))
                    intents=cursor.fetchone()
                    if (not suppressed or not intents or
                        type(suppressed[0]) is not int or
                        type(intents[0]) is not int or
                        suppressed[0]<0 or intents[0]<0):
                        raise ValueError("CANONICAL_COUNTS_UNVERIFIED")
                    checked.append({
                        "company":company,
                        "suppression_matches":suppressed[0],
                        "canonical_intent_matches":intents[0],
                        "historical_send_canonically_approved": False,
                    })
                output["status"]="CANONICAL_READ_ONLY_COUNTS_OBSERVED_NOT_SEND_CLEARANCE"
                output["checked"]=checked
                connection.rollback()
    except Exception:
        output["status"]="HELD_CANONICAL_VISIBILITY_UNVERIFIED"
        output.pop("checked",None)
        output["full_rls_visibility_verified"]=False
    return output


def main() -> int:
    report=run()
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0 if report["status"].startswith("CANONICAL_READ_ONLY_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
