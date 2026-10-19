#!/usr/bin/env python3
"""Non-mutating EmpireDB niche count service-release preflight.

Without --probe-database: code and exchange contract only, no credential access.
With --probe-database: existing DSN, repeatable-read READ ONLY and column-level
access checks; never sends mail, triggers jobs, changes tables or prints secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from empire_os.data_backends.empiredb import EmpireDbProvider
from empire_os.data_backends.postgres import (
    PostgresConnectionConfig,
    PostgresConnector,
)
from scripts.report_niche_lead_supply_empiredb import COLUMNS, IncompleteCanonicalRead
from empire_os.lead_supply_read_authority import (
    validate_reader_identity, DEDICATED_READER_LOGIN,
)

REQUIRED = ("prospects", "prospect_acquisitions", "prospect_qualifications")
OPTIONAL = (
    "prospect_entity_links", "intelligence_scores",
    "strike_packs", "buyer_subscriptions",
)
READER_ENV_KEY = "EMPIREDB_DSN"
def audit_dedicated_reader_security(dsn: str) -> dict[str, Any]:
    """Bounded PostgreSQL catalog-only reader identity/RLS scope audit.

    All queries run under an explicit database-enforced READ ONLY transaction.
    Never prints the DSN, personal data, SQL row results, or credentials.
    """
    result: dict[str, Any] = {
        "role_flags_safe": False,
        "direct_role_memberships_absent": False,
        "source_rls_policy_checks": {},
        "source_write_privileges_absent": False,
        "proven": False,
    }
    all_tables = REQUIRED + OPTIONAL
    try:
        with psycopg.connect(
            conninfo=dsn,
            connect_timeout=5,
            application_name="empire-lead-supply-security-audit",
        ) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '8s'")
            row = conn.execute(
                "SELECT oid,rolsuper,rolcreaterole,rolcreatedb,"
                " rolreplication,rolbypassrls FROM pg_catalog.pg_roles"
                " WHERE rolname=current_user"
            ).fetchone()
            if row is None:
                return result
            role_oid = row[0]
            result["role_flags_safe"] = not any(row[1:])
            memberships = conn.execute(
                "SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member=%s",
                (role_oid,),
            ).fetchone()
            result["direct_role_memberships_absent"] = memberships[0] == 0
            for table in all_tables:
                audit = conn.execute(
                    "SELECT c.relrowsecurity, c.relowner <> %s::oid, "
                    " COALESCE(bool_or(p.polpermissive"
                    " AND p.polcmd IN ('r','*')"
                    " AND %s::oid = ANY(p.polroles)"
                    " AND pg_catalog.pg_get_expr(p.polqual,c.oid)='true'), false), "
                    " COALESCE(bool_or(NOT p.polpermissive"
                    " AND p.polcmd IN ('r','*')"
                    " AND (%s::oid = ANY(p.polroles) OR 0::oid = ANY(p.polroles))), false) "
                    "FROM pg_catalog.pg_class c "
                    "LEFT JOIN pg_catalog.pg_policy p ON p.polrelid=c.oid "
                    "WHERE c.oid=pg_catalog.to_regclass(%s) "
                    "GROUP BY c.relrowsecurity,c.relowner",
                    (role_oid, role_oid, role_oid, f"public.{table}"),
                ).fetchone()
                result["source_rls_policy_checks"][table] = bool(
                    audit and audit[0] is True and audit[1] is True
                    and audit[2] is True and audit[3] is False
                )
                # PostgreSQL column-level grants and table privileges are
                # separate. Both must be free of write-capable rights.
                table_write = conn.execute(
                    "SELECT pg_catalog.has_table_privilege("
                    "current_user,%s,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
                    (f"public.{table}",),
                ).fetchone()[0]
                column_write = conn.execute(
                    "SELECT pg_catalog.has_any_column_privilege("
                    "current_user,%s,'INSERT,UPDATE,REFERENCES')",
                    (f"public.{table}",),
                ).fetchone()[0]
                if table_write or column_write:
                    result.setdefault("write_rights_violation_tables", []).append(table)
            conn.rollback()
    except Exception as exc:
        result["security_audit_error_class"] = type(exc).__name__
        return result
    result["source_write_privileges_absent"] = not result.get(
        "write_rights_violation_tables"
    )
    result["proven"] = all((
        result["role_flags_safe"],
        result["direct_role_memberships_absent"],
        result["source_write_privileges_absent"],
        all(result["source_rls_policy_checks"].values()),
    ))
    return result


def _timestamp(value: Any, now: datetime) -> int | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return max(0, int((now - dt).total_seconds()))
    except (ValueError, TypeError):
        return None


def preflight(
    repo_root: Path,
    *,
    probe_database: bool = False,
    provider: Any | None = None,
    security_audit: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("now must have timezone")
    out: dict[str, Any] = {
        "schema_version": "empire.lead_supply_readonly_preflight.v1",
        "mode": "OBSERVE",
        "database_mutation": False,
        "outbound_sent": False,
        "payment_activation": False,
        "secret_material_printed": False,
        "source_tree_ready": all(
            (repo_root / name).exists()
            for name in (
                "empire_os/lead_supply_intelligence.py",
                "empire_os/lead_territory_mrr_bridge.py",
                "empire_os/lead_territory_supply_join.py",
                "empire_os/lead_scoring_inventory_bridge.py",
                "scripts/report_niche_lead_supply_empiredb.py",
            )
        ),
        "exchange_snapshot_canonical": False,
        "exchange_snapshot_age_seconds": None,
        "exchange_snapshot_fresh_30min": False,
        "database_probe_requested": probe_database,
        "database_reader_role_verified": False,
        "dedicated_reader_rls_and_write_scope_verified": False,
        "required_table_readable": {},
        "optional_table_readable": {},
        "missing_required_privilege": False,
        "census_execution_authorized": False,
        "production_service_installed": False,
        "execution_authority": "none",
    }
    path = repo_root / "runtime/commercial_exchange/latest.json"
    try:
        exchange = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(exchange, dict):
            raise ValueError("invalid exchange")
        out["exchange_snapshot_canonical"] = (
            exchange.get("canonical_backend") == "empiredb"
            and exchange.get("source") == "canonical_empiredb_projection"
        )
        out["exchange_snapshot_age_seconds"] = _timestamp(
            exchange.get("observed_at"), moment
        )
        out["exchange_snapshot_fresh_30min"] = (
            out["exchange_snapshot_age_seconds"] is not None
            and out["exchange_snapshot_age_seconds"] <= 1800
        )
    except (OSError, ValueError, TypeError):
        pass
    if not probe_database:
        out["release_readiness"] = "CODE_ONLY_DB_ACCESS_NOT_CHECKED"
        return out
    if os.environ.get("EMPIRE_DATA_BACKEND", "empiredb").strip() != "empiredb":
        out["release_readiness"] = "HOLD_NONCANONICAL_BACKEND"
        return out
    if provider is None:
        if not os.environ.get(READER_ENV_KEY):
            out["release_readiness"] = "HOLD_READER_DSN_NOT_PROVISIONED"
            return out
        identity_ok, identity_status = validate_reader_identity(
            os.environ[READER_ENV_KEY]
        )
        out["dedicated_reader_identity_check"] = identity_status
        if not identity_ok:
            out["release_readiness"] = "HOLD_READER_IDENTITY_NOT_TRUSTED"
            return out
        security_audit = audit_dedicated_reader_security(
            os.environ[READER_ENV_KEY]
        )
        if not security_audit.get("proven"):
            out["reader_security_audit"] = security_audit
            out["release_readiness"] = "HOLD_DEDICATED_READER_RLS_OR_PRIVILEGES"
            return out
        provider = EmpireDbProvider(
            PostgresConnector(PostgresConnectionConfig.from_env())
        )
    out["reader_security_audit"] = dict(security_audit or {"proven": False})
    out["dedicated_reader_rls_and_write_scope_verified"] = (
        out["reader_security_audit"].get("proven") is True
    )
    for table in REQUIRED + OPTIONAL:
        known = table in REQUIRED
        try:
            with provider.read_only_snapshot() as reader:
                count = reader.count(table)
                # Column access verified by a SELECT LIMIT 0: not a personal-
                # data export. Count is intentionally omitted from preflight.
                reader.query(table, COLUMNS[table], limit=0)
                if count < 0:
                    raise IncompleteCanonicalRead("negative count")
            out["required_table_readable" if known else "optional_table_readable"][table] = True
        except Exception as exc:
            out["required_table_readable" if known else "optional_table_readable"][table] = False
            out.setdefault("reader_error_classes", {})[table] = type(exc).__name__
    out["missing_required_privilege"] = not all(
        out["required_table_readable"].values()
    )
    out["database_reader_role_verified"] = not out["missing_required_privilege"]
    out["release_readiness"] = (
        "READONLY_READER_CAPABILITY_READY_FOR_FOUNDER_REVIEW"
        if out["source_tree_ready"]
        and out["exchange_snapshot_canonical"]
        and out["exchange_snapshot_fresh_30min"]
        and out["database_reader_role_verified"]
        and out["dedicated_reader_rls_and_write_scope_verified"]
        else "HOLD_REVIEW_FAILED_PRECONDITION"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--probe-database", action="store_true")
    args = parser.parse_args()
    result = preflight(args.repo_root, probe_database=args.probe_database)
    print(json.dumps(result, sort_keys=True))
    if args.probe_database and result.get("release_readiness") != (
        "READONLY_READER_CAPABILITY_READY_FOR_FOUNDER_REVIEW"
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
