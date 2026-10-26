"""Restricted runtime adapter for evidence-backed TAM market intelligence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from empire_os.tam_isolated_credential import load_tam_isolated_dsn
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


def _validate_restricted_tam_dsn(
    dsn: str, *, login: str = "empire_intelligence_materializer_login"
) -> str:
    """Restrict canonical TAM data reads to the local capability login."""
    if not isinstance(dsn, str) or not dsn.strip() or len(dsn) > 2048:
        raise ValueError("restricted TAM materializer DSN required")
    try:
        from psycopg.conninfo import conninfo_to_dict
        config = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError("invalid restricted TAM reader DSN") from None
    if (
        login not in (
            "empire_intelligence_materializer_login",
            "empire_tam_market_login",
        ) or config.get("user") != login
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
    clean = _validate_restricted_tam_dsn(
        dsn, login="empire_tam_market_login"
    )
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
                    "SET LOCAL ROLE empire_tam_market_reader"
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



_SCOPED_READER_RPC = "public.get_tam_market_observations_scoped(text[],text[],integer)"
_SCOPED_SECTORS = frozenset(("roofing", "solar", "insurance"))
_SCOPED_COUNTRIES = frozenset(("GB", "US"))


def _approved_scoped_markets(
    industries: Iterable[str], countries: Iterable[str],
    limit: int,
) -> tuple[list[str], list[str]]:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("scoped TAM reader limit must be 1-1000")
    active_i = list(industries)
    active_c = list(countries)
    if (
        not active_i or not active_c
        or len(active_i) > 3 or len(active_c) > 2
        or any(type(v) is not str for v in (*active_i, *active_c))
        or len(set(active_i)) != len(active_i)
        or len(set(active_c)) != len(active_c)
        or not set(active_i) <= _SCOPED_SECTORS
        or not set(active_c) <= _SCOPED_COUNTRIES
        or len(active_i) * len(active_c) > limit
    ):
        raise ValueError("scoped TAM markets outside approved research scope")
    return sorted(active_i), sorted(active_c)


def probe_isolated_tam_scoped_capability(
    dsn: str, *, connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Inspect only catalog metadata for separately held migration 044."""
    _validate_restricted_tam_dsn(dsn, login="empire_tam_market_login")
    original = probe_isolated_tam_reader_capability(
        dsn, connect_factory=connect_factory,
    )
    if original.get("isolated_tam_contract_verified") is not True:
        return {
            "scoped_contract_verified": False,
            "status": "EXISTING_ISOLATED_TAM_CONTRACT_NOT_VERIFIED",
            "no_data_rows_read": True,
            "execution_authority": "none",
        }
    if connect_factory is None:
        import psycopg
        connect_factory = lambda configured: psycopg.connect(
            configured, connect_timeout=3
        )
    try:
        with connect_factory(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE empire_tam_market_reader")
                cur.execute("""
                    SELECT
                       to_regprocedure(
                         'public.get_tam_market_observations_scoped(text[],text[],integer)'
                       ) IS NOT NULL,
                       COALESCE((
                         SELECT p.prosecdef
                            AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                                           WHERE rolname='empiredb_migrator')
                            AND p.proconfig @> ARRAY['search_path=""']::text[]
                            AND p.provolatile='s'
                            AND p.prorettype='pg_catalog.jsonb'::regtype
                         FROM pg_catalog.pg_proc p
                         WHERE p.oid=to_regprocedure(
                           'public.get_tam_market_observations_scoped(text[],text[],integer)'
                         )
                       ),false),
                       COALESCE(has_function_privilege(
                         current_user,
                         to_regprocedure(
                           'public.get_tam_market_observations_scoped(text[],text[],integer)'
                         ),'EXECUTE'),false),
                       COALESCE(has_function_privilege(
                         'empire_intelligence_materializer',
                         to_regprocedure(
                           'public.get_tam_market_observations_scoped(text[],text[],integer)'
                         ),'EXECUTE'),false),
                       COALESCE(has_function_privilege(
                         'empiredb_app',
                         to_regprocedure(
                           'public.get_tam_market_observations_scoped(text[],text[],integer)'
                         ),'EXECUTE'),false)
                """)
                result = cur.fetchone()
    except Exception:
        result = None
    passed = (
        isinstance(result, (tuple, list)) and len(result) == 5
        and all(v is True for v in result[:3])
        and all(v is False for v in result[3:])
    )
    return {
        "scoped_contract_verified": passed,
        "status": "PASS" if passed else "SCOPED_READER_NOT_VERIFIED",
        "no_data_rows_read": True,
        "execution_authority": "none",
    }


def fetch_tam_scoped_market_sample(
    dsn: str, *, industries: Iterable[str], countries: Iterable[str],
    limit: int = 1000, connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Return bounded scoped rows + explicit zero-evidence market coverage."""
    dsn = _validate_restricted_tam_dsn(
        dsn, login="empire_tam_market_login",
    )
    approved_i, approved_c = _approved_scoped_markets(
        industries, countries, limit,
    )
    if connect_factory is None:
        import psycopg
        connect_factory = lambda configured: psycopg.connect(
            configured, connect_timeout=5
        )
    try:
        with connect_factory(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE empire_tam_market_reader")
                cur.execute(
                    "SELECT public.get_tam_market_observations_scoped(%s,%s,%s)",
                    (approved_i, approved_c, limit),
                )
                row = cur.fetchone()
    except Exception:
        raise RuntimeError("isolated scoped TAM market read failed") from None
    if (
        not isinstance(row, (tuple, list)) or len(row) != 1
        or not isinstance(row[0], Mapping)
    ):
        raise ValueError("scoped TAM reader response invalid")
    doc = dict(row[0])
    scopes = [(i, c) for i in approved_i for c in approved_c]
    expected = set(scopes)
    rows = doc.get("rows")
    coverage = doc.get("scope_coverage")
    if (
        doc.get("schema_version") != "empire.tam-scoped-reader.v1"
        or doc.get("selection_method") != "MARKET_QUOTA_SAMPLED"
        or doc.get("source_population_complete") is not False
        or doc.get("buyer_intent_inferred") is not False
        or doc.get("tam_inferred_from_roster") is not False
        or doc.get("execution_authority") != "none"
        or type(doc.get("requested_limit")) is not int
        or doc["requested_limit"] != limit
        or type(doc.get("requested_scope_count")) is not int
        or doc["requested_scope_count"] != len(scopes)
        or not isinstance(rows, list) or len(rows) > limit
        or not isinstance(coverage, list) or len(coverage) != len(scopes)
    ):
        raise ValueError("scoped TAM reader response violates research contract")
    observed: dict[tuple[str, str], int] = {key: 0 for key in scopes}
    seen_entities: set[tuple[str, str, str]] = set()
    for record in rows:
        if not isinstance(record, Mapping):
            raise ValueError("scoped TAM response has invalid source row")
        industry, country = record.get("industry"), record.get("country_code")
        key = (industry, country)
        if key not in expected or record.get("execution_authority") != "none":
            raise ValueError("scoped TAM result contains unapproved market")
        entity = record.get("entity_id")
        if not isinstance(entity, str) or not entity.strip():
            raise ValueError("scoped TAM row missing canonical entity identity")
        token = (industry, country, entity)
        if token in seen_entities:
            raise ValueError("scoped TAM sample duplicated a canonical entity")
        seen_entities.add(token)
        observed[key] += 1
    seen: set[tuple[str, str]] = set()
    for entry in coverage:
        if not isinstance(entry, Mapping):
            raise ValueError("scoped TAM coverage invalid")
        key = (entry.get("industry"), entry.get("country_code"))
        if key not in expected or key in seen:
            raise ValueError("scoped TAM coverage missing/duplicate market")
        seen.add(key)
        rank = scopes.index(key)
        quota = limit // len(scopes) + (rank < limit % len(scopes))
        if (
            type(entry.get("sample_quota")) is not int
            or entry["sample_quota"] != quota
            or type(entry.get("selected_count")) is not int
            or entry["selected_count"] != observed[key]
            or observed[key] > quota
            or entry.get("population_complete") is not False
        ):
            raise ValueError("scoped TAM coverage inconsistent with source rows")
    doc["rows"] = [dict(x) for x in rows]
    doc["scope_coverage"] = [dict(x) for x in coverage]
    return doc

def _probe_role_capability(
    dsn: str, *,
    login: str, capability_role: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Read-only catalog proof using the dedicated restricted EmpireDB login.

    No market rows, secrets, migrations, GRANTs, or privileged fallback.
    Even a valid function does not imply that a tenant-authenticated SaaS
    reader or source population is configured.
    """
    if (login, capability_role) not in (
        ("empire_intelligence_materializer_login",
         "empire_intelligence_materializer"),
        ("empire_tam_market_login", "empire_tam_market_reader"),
    ):
        raise ValueError("unsupported TAM capability identity")
    _validate_restricted_tam_dsn(dsn, login=login)
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
                cursor.execute("SET LOCAL ROLE " + capability_role)
                cursor.execute("""
                    SELECT
                        session_user = %s,
                        current_user = %s,
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
                                AND p.proconfig @> ARRAY['search_path=""']::text[]
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
                """, (login, capability_role))
                found = cursor.fetchone()
    except Exception:
        return {
            "status":"RESTRICTED_CATALOG_PROBE_UNAVAILABLE",
            ("isolated_tam_contract_verified"
             if login == "empire_tam_market_login"
             else "migration_028_contract_verified"):False,
            "no_data_rows_read":True,
            "execution_authority":"none",
        }
    if not isinstance(found,(list,tuple)) or len(found)!=11:
        return {
            "status":"INVALID_RESTRICTED_CATALOG_RESPONSE",
            ("isolated_tam_contract_verified"
             if login == "empire_tam_market_login"
             else "migration_028_contract_verified"):False,
            "no_data_rows_read":True,
            "execution_authority":"none",
        }
    (login_verified, role_verified, exists, definer, exec_allowed,
     *grants_and_tables) = found
    # PostgreSQL privilege list succeeds if ANY listed direct privilege is
    # effective, including write/DDL privileges; NONE may be inherited.
    direct_grants = grants_and_tables[:3]
    source_tables_exist = grants_and_tables[3:]
    verified = (
        all(v is True for v in (
            login_verified, role_verified, exists, definer, exec_allowed,
            *source_tables_exist,
        ))
        and all(v is False for v in direct_grants)
    )
    return {
        "status":"PASS" if verified else "RESTRICTED_CATALOG_CONTRACT_INCOMPLETE",
        ("isolated_tam_contract_verified"
         if login == "empire_tam_market_login"
         else "migration_028_contract_verified"):verified,
        "restricted_login_verified":login_verified is True,
        "capability_role_verified":role_verified is True,
        "function_exists":exists is True,
        "security_definer_verified":definer is True,
        "capability_execute_verified":exec_allowed is True,
        "source_tables_present":all(v is True for v in source_tables_exist),
        "source_table_direct_read_grants":any(v is True for v in direct_grants),
        "no_data_rows_read":True,
        "execution_authority":"none",
    }



def probe_tam_reader_capability(
    dsn: str, *, connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Legacy Market GPS catalog diagnosis; never permits a TAM refresh."""
    return _probe_role_capability(
        dsn,
        login="empire_intelligence_materializer_login",
        capability_role="empire_intelligence_materializer",
        connect_factory=connect_factory,
    )


def probe_isolated_tam_reader_capability(
    dsn: str, *, connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Read-only preflight for the isolated, not-yet-activated TAM credential."""
    return _probe_role_capability(
        dsn, login="empire_tam_market_login",
        capability_role="empire_tam_market_reader",
        connect_factory=connect_factory,
    )

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

    # Only the isolated systemd credential is permissible. No fallback to the
    # live generic Market GPS materializer; no plaintext environment DSN.
    dsn = load_tam_isolated_dsn()
    # A mere DSN is not authorization to read company rows. Prove the live
    # restricted function/role/direct-grant contract immediately before the
    # first data read, not just from an old supervisor catalog artifact.
    reader_mode = os.environ.get("EMPIRE_TAM_READER_MODE", "legacy")
    scoped_sample = None
    if reader_mode == "scoped_v1":
        # Migration 044 is separately held. No fallback to the legacy global
        # sample if it has not been independently deployed and verified.
        requested_i, requested_c = _approved_scoped_markets(
            active_industries, active_countries, limit,
        )
        capability = probe_isolated_tam_scoped_capability(
            dsn, connect_factory=connect_factory,
        )
        if capability.get("scoped_contract_verified") is not True:
            raise RuntimeError("TAM scoped catalog preflight not verified")
        scoped_sample = fetch_tam_scoped_market_sample(
            dsn, industries=requested_i, countries=requested_c,
            limit=limit, connect_factory=connect_factory,
        )
        rows = scoped_sample["rows"]
    elif reader_mode == "legacy":
        capability = probe_isolated_tam_reader_capability(
            dsn, connect_factory=connect_factory,
        )
        if capability.get("isolated_tam_contract_verified") is not True:
            raise RuntimeError("TAM isolated catalog preflight not verified")
        rows = fetch_tam_market_observations_postgres(
            dsn, limit=limit, connect_factory=connect_factory,
        )
    else:
        raise RuntimeError("TAM reader mode not approved")
    # Active market scope is a hard output/data minimisation boundary,
    # not just a label used to classify new-country opportunities.
    selected_industries = {v.strip().casefold() for v in active_industries}
    selected_countries = {v.strip().upper() for v in active_countries}
    scoped_rows = [
        row for row in rows
        if str(row.get("industry") or "").strip().casefold()
            in selected_industries
        and str(row.get("country_code") or "").strip().upper()
            in selected_countries
    ]
    payload = build_tam_runtime(
        scoped_rows,
        tenant_id=tenant_id,
        active_industries=active_industries,
        active_countries=active_countries,
    )
    payload["raw_source_rows_examined"] = len(rows)
    payload["out_of_scope_rows_excluded"] = len(rows) - len(scoped_rows)
    payload["approved_research_industries"] = sorted(selected_industries)
    payload["approved_research_countries"] = sorted(selected_countries)
    # Neither mode is a complete population census.
    payload["source_population_complete"] = False
    if scoped_sample is not None:
        payload["sampling_method"] = "MARKET_QUOTA_SAMPLED"
        payload["requested_sample_limit"] = scoped_sample["requested_limit"]
        payload["requested_market_scope_count"] = scoped_sample[
            "requested_scope_count"
        ]
        payload["market_scope_sample_coverage"] = scoped_sample[
            "scope_coverage"
        ]
        payload["market_scope_zero_observation_count"] = sum(
            x["selected_count"] == 0
            for x in scoped_sample["scope_coverage"]
        )
        # This is the number of selected rows returned by the DB, NOT a
        # count of every candidate examined during SQL query execution.
        payload["raw_source_rows_examined"] = len(rows)
        payload["source_rows_examined_meaning"] = "RETURNED_SAMPLE_ROWS_ONLY"
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
    parser.add_argument("--portfolio", action="store_true",
                        help="Read saved TAM and Exchange receipts only; aggregate portfolio view.")
    args = parser.parse_args()
    if sum((args.preflight, args.refresh, args.portfolio)) > 1:
        parser.error("--preflight, --refresh and --portfolio are mutually exclusive")

    if args.portfolio:
        from empire_os.tam_revenue_portfolio import read_tam_revenue_portfolio_from_runtime
        result = read_tam_revenue_portfolio_from_runtime(
            Path(args.repo_root) / "runtime"
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0

    if args.preflight:
        try:
            dsn = load_tam_isolated_dsn()
            payload = probe_isolated_tam_reader_capability(dsn)
        except (ValueError, RuntimeError, OSError):
            payload = {
                "status":"RESTRICTED_TAM_CREDENTIAL_UNAVAILABLE",
                "migration_028_contract_verified":False,
                "no_data_rows_read":True,
                "execution_authority":"none",
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("isolated_tam_contract_verified") is True else 3

    if args.refresh:
        payload = refresh_tam_market_runtime(
            args.repo_root,
            limit=args.limit,
        )
    else:
        payload = build_tam_runtime_snapshot(args.repo_root)
    if args.refresh:
        # Service journals must never contain company names, evidence URLs,
        # contact details, tenant source rows, or credential information.
        public = {
            "schema_version": "empire.tam_runtime_refresh_receipt.v1",
            "mode": "OBSERVE",
            "status": "CANONICAL_SNAPSHOT_WRITTEN",
            "source_row_count": payload.get("source_row_count"),
            "market_scope_count": payload.get("market_scope_count"),
            "opportunity_class_count": len(payload.get("opportunity_classes") or []),
            "tam_inferred_from_observed_roster": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
        print(json.dumps(public, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
