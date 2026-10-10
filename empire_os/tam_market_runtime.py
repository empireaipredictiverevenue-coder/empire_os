"""Restricted runtime adapter for evidence-backed TAM market intelligence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from empire_os.intelligence_materializer_env import load_materializer_env
from empire_os.tam_market_intelligence import (
    MarketEntityObservation,
    TamCountEvidence,
    build_tam_market_intelligence,
)


OUTPUT = Path("runtime/tam_market_intelligence/latest.json")


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.environ.get(name, "").split(",")
        if item.strip()
    )


def _validate_restricted_tam_dsn(dsn: str) -> str:
    """Restrict canonical TAM data reads to the local capability login."""
    if not isinstance(dsn, str) or not dsn.strip() or len(dsn) > 2048:
        raise ValueError("restricted TAM materializer DSN required")
    try:
        from psycopg.conninfo import conninfo_to_dict
        config = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError("invalid restricted TAM reader DSN") from None
    if (
        config.get("user") != "empire_intelligence_materializer_login"
        or config.get("dbname") != "empiredb"
        or not config.get("password")
        or config.get("host") not in (
            "localhost", "127.0.0.1", "::1", "/var/run/postgresql"
        )
        or config.get("service") or config.get("options")
        or set(config) - {
            "user", "password", "dbname", "host", "port", "connect_timeout"
        }
    ):
        raise ValueError("dedicated local EmpireDB TAM login required")
    return dsn.strip()


def fetch_tam_market_observations_postgres(
    dsn: str,
    *,
    limit: int = 1000,
    connect_factory: Callable | None = None,
) -> list[dict[str, Any]]:
    clean = _validate_restricted_tam_dsn(dsn)
    # Do not silently clip requested scope, and reject booleans and floats.
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise ValueError("TAM reader limit must be an integer in 1-5000")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg required for TAM runtime") from exc
        connect_factory = lambda configured: psycopg.connect(
            configured, connect_timeout=5
        )

    try:
        with connect_factory(clean) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                cursor.execute(
                    "SELECT public.get_tam_market_observations(%s)",
                    (limit,),
                )
                row = cursor.fetchone()
    except Exception:
        # Prevent leaking DSN/credentials via chained psycopg diagnostics.
        raise RuntimeError("restricted TAM market read failed") from None

    if not isinstance(row, (tuple, list)) or len(row) != 1:
        raise ValueError("TAM market RPC returned invalid row shape")
    payload = row[0]
    if (not isinstance(payload, list) or len(payload) > limit
            or any(not isinstance(item, Mapping) for item in payload)):
        raise ValueError("TAM market RPC returned invalid payload")
    return [dict(item) for item in payload]


def probe_tam_reader_capability(
    dsn: str,
    *,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Read-only catalog proof using the dedicated restricted EmpireDB login.

    No market rows, secrets, migrations, GRANTs, or privileged fallback.
    Even a valid function does not imply that a tenant-authenticated SaaS
    reader or source population is configured.
    """
    _validate_restricted_tam_dsn(dsn)
    if connect_factory is None:
        import psycopg
        # The passive catalog check must never block the existing Market GPS
        # oneshot for an unbounded database connection attempt.
        connect_factory = lambda configured: psycopg.connect(
            configured, connect_timeout=3
        )
    try:
        with connect_factory(dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL ROLE empire_intelligence_materializer")
                cursor.execute("""
                    SELECT
                        session_user = 'empire_intelligence_materializer_login',
                        current_user = 'empire_intelligence_materializer',
                        to_regprocedure(
                            'public.get_tam_market_observations(integer)'
                        ) IS NOT NULL,
                        COALESCE(
                            (SELECT
                                p.prosecdef
                                AND p.proowner = (
                                    SELECT oid FROM pg_catalog.pg_roles
                                    WHERE rolname = 'empiredb_migrator'
                                )
                                AND p.proconfig @> ARRAY['search_path=']::text[]
                                AND p.provolatile = 's'
                                AND p.prorettype = 'pg_catalog.jsonb'::regtype
                             FROM pg_catalog.pg_proc p
                             WHERE p.oid = to_regprocedure(
                                 'public.get_tam_market_observations(integer)'
                             )),
                            FALSE
                        ),
                        COALESCE(
                            has_function_privilege(
                                current_user,
                                to_regprocedure(
                                    'public.get_tam_market_observations(integer)'
                                ),
                                'EXECUTE'
                            ),
                            FALSE
                        ),
                        COALESCE(
                            has_table_privilege(
                                current_user,
                                to_regclass('public.prospect_acquisitions'),
                                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
                            ),
                            FALSE
                        ),
                        COALESCE(
                            has_table_privilege(
                                current_user,
                                to_regclass('public.prospect_entity_links'),
                                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
                            ),
                            FALSE
                        ),
                        COALESCE(
                            has_table_privilege(
                                current_user,
                                to_regclass('public.business_entities'),
                                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
                            ),
                            FALSE
                        ),
                        to_regclass('public.prospect_acquisitions') IS NOT NULL,
                        to_regclass('public.prospect_entity_links') IS NOT NULL,
                        to_regclass('public.business_entities') IS NOT NULL
                """)
                found = cursor.fetchone()
    except Exception:
        return {
            "status":"RESTRICTED_CATALOG_PROBE_UNAVAILABLE",
            "migration_028_contract_verified":False,
            "no_data_rows_read":True,
            "execution_authority":"none",
        }
    if not isinstance(found,(list,tuple)) or len(found)!=11:
        return {
            "status":"INVALID_RESTRICTED_CATALOG_RESPONSE",
            "migration_028_contract_verified":False,
            "no_data_rows_read":True,
            "execution_authority":"none",
        }
    (login, capability, exists, definer, exec_allowed,
     *grants_and_tables) = found
    # PostgreSQL privilege list succeeds if ANY listed direct privilege is
    # effective, including write/DDL privileges; NONE may be inherited.
    direct_grants = grants_and_tables[:3]
    source_tables_exist = grants_and_tables[3:]
    verified = (
        all(v is True for v in (
            login, capability, exists, definer, exec_allowed,
            *source_tables_exist,
        ))
        and all(v is False for v in direct_grants)
    )
    return {
        "status":"PASS" if verified else "RESTRICTED_CATALOG_CONTRACT_INCOMPLETE",
        "migration_028_contract_verified":verified,
        "restricted_login_verified":login is True,
        "capability_role_verified":capability is True,
        "function_exists":exists is True,
        "security_definer_verified":definer is True,
        "capability_execute_verified":exec_allowed is True,
        "source_tables_present":all(v is True for v in source_tables_exist),
        "source_table_direct_read_grants":any(v is True for v in direct_grants),
        "no_data_rows_read":True,
        "execution_authority":"none",
    }


def build_tam_runtime(
    rows: Iterable[Mapping[str, Any]],
    *,
    tenant_id: str,
    active_industries: Iterable[str],
    active_countries: Iterable[str],
    tam_evidence: Iterable[TamCountEvidence] = (),
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    industries = tuple(
        str(value).strip()
        for value in active_industries
        if str(value or "").strip()
    )
    countries = tuple(
        str(value).strip().upper()
        for value in active_countries
        if str(value or "").strip()
    )
    if not tenant:
        raise ValueError("TAM tenant id required")
    if not industries:
        raise ValueError("active TAM industries required")
    if not countries:
        raise ValueError("active TAM countries required")

    observations: list[MarketEntityObservation] = []
    for row in rows:
        if str(row.get("execution_authority") or "none") != "none":
            raise ValueError("TAM source row has execution authority")
        # A cross-tenant or explicitly foreign tenant row must never be
        # silently rebound to the current research tenant.
        row_tenant = row.get("tenant_id")
        if row_tenant is not None and str(row_tenant).strip() != tenant:
            raise ValueError("mixed tenant TAM runtime observation")
        observations.append(
            MarketEntityObservation(
                tenant_id=tenant,
                entity_id=str(row.get("entity_id") or "").strip(),
                company_name=str(row.get("company_name") or "").strip(),
                industry=str(row.get("industry") or "").strip(),
                country_code=str(row.get("country_code") or "").strip(),
                source_ref=str(row.get("source_ref") or "").strip(),
                observed_at=str(row.get("observed_at") or "").strip(),
            )
        )

    result = build_tam_market_intelligence(
        tenant_id=tenant,
        observations=observations,
        active_industries=industries,
        active_countries=countries,
        tam_evidence=tam_evidence,
    )
    return {
        **result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "empiredb_restricted_tam_reader",
        "source_row_count": len(observations),
        "canonical_data": True,
        # The restricted SQL function is platform evidence without a tenant
        # predicate; requested report tenant is a research scope, not proof
        # of customer login/tenant authority.
        "tenant_source_scope_verified": False,
        "data_scope": "PLATFORM_MARKET_RESEARCH_ONLY",
        "external_execution": False,
    }


def write_tam_snapshot(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    path = Path(repo_root).resolve() / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("unsafe TAM snapshot destination")
    tmp = path.with_suffix(".tmp")
    if tmp.is_symlink():
        raise ValueError("unsafe TAM temporary destination")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return path


def refresh_tam_market_runtime(
    repo_root: str | Path,
    *,
    limit: int = 1000,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    tenant_id = os.environ.get("EMPIRE_TAM_TENANT_ID", "").strip()
    active_industries = _csv_env("EMPIRE_TAM_ACTIVE_INDUSTRIES")
    active_countries = _csv_env("EMPIRE_TAM_ACTIVE_COUNTRIES")
    if not tenant_id or not active_industries or not active_countries:
        raise RuntimeError("TAM runtime configuration incomplete")

    env = load_materializer_env()
    # A mere DSN is not authorization to read company rows. Prove the live
    # restricted function/role/direct-grant contract immediately before the
    # first data read, not just from an old supervisor catalog artifact.
    capability = probe_tam_reader_capability(
        env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"],
        connect_factory=connect_factory,
    )
    if capability.get("migration_028_contract_verified") is not True:
        raise RuntimeError("TAM restricted catalog preflight not verified")
    rows = fetch_tam_market_observations_postgres(
        env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"],
        limit=limit,
        connect_factory=connect_factory,
    )
    payload = build_tam_runtime(
        rows,
        tenant_id=tenant_id,
        active_industries=active_industries,
        active_countries=active_countries,
    )
    write_tam_snapshot(repo_root, payload)
    return payload


def build_tam_runtime_snapshot(repo_root: str | Path) -> dict[str, Any]:
    path = Path(repo_root).resolve() / OUTPUT
    from empire_os.revenue_completion_supervisor import tam_snapshot_truth

    def blocked(reason: str) -> dict[str, Any]:
        return {
            "available": False,
            "schema_version": "empire.tam-market-intelligence.v1",
            "mode": "OBSERVE",
            "reason_code": reason,
            "market_scopes": [],
            "opportunity_classes": [],
            "execution_authority": "none",
        }

    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_mode & 0o077
                or path.stat().st_size > 8_000_000):
            return blocked("CANONICAL_SNAPSHOT_ABSENT_OR_UNSAFE")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return blocked("CANONICAL_SNAPSHOT_UNREADABLE")
    truth = tam_snapshot_truth(payload)
    if not truth["available"]:
        return blocked(truth["reason_code"])
    # available belongs to the verified reader, not the JSON itself.
    return {**payload, "available": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--preflight", action="store_true",
                        help="Inspect restricted catalog capability; never read market rows.")
    args = parser.parse_args()
    if args.preflight and args.refresh:
        parser.error("--preflight and --refresh are mutually exclusive")

    if args.preflight:
        try:
            env = load_materializer_env()
            payload = probe_tam_reader_capability(
                env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"]
            )
        except (ValueError, RuntimeError, OSError):
            payload = {
                "status":"RESTRICTED_TAM_CREDENTIAL_UNAVAILABLE",
                "migration_028_contract_verified":False,
                "no_data_rows_read":True,
                "execution_authority":"none",
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("migration_028_contract_verified") is True else 3

    if args.refresh:
        payload = refresh_tam_market_runtime(
            args.repo_root,
            limit=args.limit,
        )
    else:
        payload = build_tam_runtime_snapshot(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
