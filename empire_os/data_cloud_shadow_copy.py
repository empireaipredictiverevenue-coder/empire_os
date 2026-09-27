"""Governed PostgREST-compatible -> EmpireDB shadow copy.

Migration-only infrastructure. This module has no authority to change the
canonical backend, delete source rows, truncate target tables, or perform a
production cutover.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ISO_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


@dataclass(frozen=True)
class ShadowTable:
    name: str
    primary_key: str = "id"
    parents: tuple[str, ...] = ()


SHADOW_TABLES: tuple[ShadowTable, ...] = (
    ShadowTable("prospects"),
    ShadowTable("business_entities"),
    ShadowTable("buyers"),
    ShadowTable("strike_packs"),
    ShadowTable("crypto_payment_requests"),
    ShadowTable("commercial_products"),
    ShadowTable("gtm_opportunities"),
    ShadowTable("intelligence_sources"),
    ShadowTable("intelligence_people"),
    ShadowTable("intelligence_segments"),
    ShadowTable("enriched_leads"),
    ShadowTable("outbound_suppressions"),
    ShadowTable("astra_observer_tokens", "token_sha256"),
    ShadowTable("commercial_product_versions", parents=("commercial_products",)),
    ShadowTable(
        "commercial_product_catalog_events",
        parents=("commercial_products", "commercial_product_versions"),
    ),
    ShadowTable("gtm_jobs", parents=("gtm_opportunities",)),
    ShadowTable("gtm_experiments", parents=("gtm_opportunities",)),
    ShadowTable("prospect_identity_claims", "identity_key", parents=("prospects",)),
    ShadowTable("prospect_acquisitions", parents=("prospects",)),
    ShadowTable(
        "prospect_entity_links",
        parents=("prospects", "business_entities"),
    ),
    ShadowTable(
        "business_entity_conflicts",
        parents=("prospects", "business_entities"),
    ),
    ShadowTable(
        "prospect_qualifications",
        parents=("prospects", "business_entities"),
    ),
    ShadowTable(
        "buyer_subscriptions",
        parents=("buyers", "strike_packs"),
    ),
    ShadowTable("buyer_commercial_evidence", parents=("buyers",)),
    ShadowTable(
        "buyer_candidate_reviews",
        parents=("prospects", "business_entities"),
    ),
    ShadowTable(
        "buyer_candidate_review_events",
        parents=("buyer_candidate_reviews",),
    ),
    ShadowTable(
        "buyer_scout_candidates",
        parents=("buyers", "prospects"),
    ),
    ShadowTable(
        "fulfilment_orders",
        parents=(
            "prospects",
            "business_entities",
            "buyers",
            "commercial_products",
            "gtm_opportunities",
        ),
    ),
    ShadowTable(
        "outbound_intents",
        parents=("prospects", "business_entities", "buyers", "gtm_opportunities"),
    ),
    ShadowTable("outbound_events", parents=("outbound_intents",)),
    ShadowTable("outbound_replies", parents=("outbound_intents",)),
    ShadowTable(
        "closer_cases",
        parents=(
            "outbound_intents",
            "outbound_replies",
            "prospects",
            "business_entities",
            "buyers",
            "gtm_opportunities",
            "fulfilment_orders",
        ),
    ),
    ShadowTable(
        "commercial_evidence_registry",
        parents=("buyers", "closer_cases", "fulfilment_orders"),
    ),
    ShadowTable(
        "commercial_events",
        parents=(
            "prospects",
            "business_entities",
            "buyers",
            "commercial_products",
            "gtm_opportunities",
            "gtm_jobs",
            "fulfilment_orders",
        ),
    ),
    ShadowTable(
        "intelligence_signals",
        parents=("business_entities", "intelligence_sources"),
    ),
    ShadowTable("intelligence_facts", parents=("intelligence_sources",)),
    ShadowTable(
        "intelligence_outcomes",
        parents=("business_entities", "intelligence_people"),
    ),
    ShadowTable(
        "intelligence_contact_points",
        parents=("business_entities", "intelligence_people", "intelligence_sources"),
    ),
    ShadowTable("intelligence_scores"),
    ShadowTable("outreach_log", parents=("enriched_leads",)),
)


def _safe_ident(value: str) -> str:
    if not _IDENT.fullmatch(value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


def validate_manifest(tables: Sequence[ShadowTable] = SHADOW_TABLES) -> None:
    names = [item.name for item in tables]
    if len(names) != len(set(names)):
        raise ValueError("shadow-copy manifest contains duplicate tables")
    all_names = set(names)
    seen: set[str] = set()
    for item in tables:
        _safe_ident(item.name)
        _safe_ident(item.primary_key)
        missing = [parent for parent in item.parents if parent not in all_names]
        if missing:
            raise ValueError(f"{item.name}: unknown parent(s): {missing}")
        late = [parent for parent in item.parents if parent not in seen]
        if late:
            raise ValueError(f"{item.name}: parent(s) appear after child: {late}")
        seen.add(item.name)


def resolve_tables(names: Sequence[str] | None) -> tuple[ShadowTable, ...]:
    validate_manifest()
    if not names:
        return SHADOW_TABLES
    requested = {name.strip() for name in names if name.strip()}
    known = {item.name for item in SHADOW_TABLES}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError(f"unknown shadow-copy tables: {unknown}")
    selected: list[ShadowTable] = []
    required = set(requested)
    changed = True
    while changed:
        changed = False
        for item in SHADOW_TABLES:
            if item.name in required:
                for parent in item.parents:
                    if parent not in required:
                        required.add(parent)
                        changed = True
    for item in SHADOW_TABLES:
        if item.name in required:
            selected.append(item)
    return tuple(selected)


def _number_text(value: int | float | Decimal) -> str:
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if number == 0:
        return "0"
    normalized = number.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return {"$number": _number_text(value)}
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        if _ISO_TIMESTAMP.fullmatch(value):
            if value.endswith("Z"):
                return value[:-1] + "+00:00"
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return str(value)


def canonical_row_bytes(row: Mapping[str, Any]) -> bytes:
    payload = json.dumps(
        _normalize(dict(row)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return payload.encode("utf-8")


def digest_rows(rows: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_row_bytes(row))
        digest.update(b"\n")
    return digest.hexdigest()


class RestShadowSource:
    """Read-only PostgREST-compatible source adapter."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        table: str,
        query: Mapping[str, str],
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> tuple[Any, Mapping[str, str]]:
        table = _safe_ident(table)
        encoded = urllib.parse.urlencode(query, safe="*,().:")
        url = f"{self.api_url}/{urllib.parse.quote(table)}?{encoded}"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "empire-shadow-copy/1",
        }
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(
            request,
            timeout=self.timeout_seconds,
        ) as response:
            body = response.read()
            payload = json.loads(body.decode("utf-8")) if body else []
            return payload, dict(response.headers.items())

    def exact_count(self, table: str, primary_key: str) -> int:
        _, headers = self._request(
            table,
            {"select": _safe_ident(primary_key), "limit": "1"},
            extra_headers={"Prefer": "count=exact", "Range": "0-0"},
        )
        content_range = (
            headers.get("Content-Range")
            or headers.get("content-range")
            or ""
        )
        if "/" not in content_range:
            raise RuntimeError(
                f"{table}: exact count response missing Content-Range"
            )
        total = content_range.rsplit("/", 1)[1]
        if total == "*":
            raise RuntimeError(f"{table}: source returned an inexact count")
        return int(total)

    def page(
        self,
        table: str,
        primary_key: str,
        *,
        after: object | None,
        limit: int,
        columns: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        primary_key = _safe_ident(primary_key)
        select = ",".join(_safe_ident(item) for item in columns) if columns else "*"
        query = {
            "select": select,
            "order": f"{primary_key}.asc",
            "limit": str(limit),
        }
        if after is not None:
            query[primary_key] = f"gt.{after}"
        payload, _ = self._request(table, query)
        if not isinstance(payload, list):
            raise RuntimeError(f"{table}: source returned non-list payload")
        return [dict(row) for row in payload]

    def all_rows(
        self,
        table: str,
        primary_key: str,
        *,
        limit: int,
        columns: Sequence[str] | None = None,
    ) -> Iterable[list[dict[str, Any]]]:
        after: object | None = None
        while True:
            rows = self.page(
                table,
                primary_key,
                after=after,
                limit=limit,
                columns=columns,
            )
            if not rows:
                return
            yield rows
            after = rows[-1][primary_key]
            if len(rows) < limit:
                return


class EmpireDbShadowTarget:
    """Target adapter that can write only to the explicit shadow manifest."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _connect(self) -> psycopg.Connection[Any]:
        connection = psycopg.connect(
            self.dsn,
            connect_timeout=5,
            application_name="empire-shadow-copy",
        )
        connection.execute("SET ROLE empiredb_migrator")
        connection.execute("SET statement_timeout = '5min'")
        return connection

    def columns(self, table: str) -> list[tuple[str, str]]:
        _safe_ident(table)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
        if not rows:
            raise RuntimeError(f"{table}: target table does not exist")
        return [(str(name), str(data_type)) for name, data_type in rows]

    def exact_count(self, table: str) -> int:
        table = _safe_ident(table)
        with self._connect() as connection:
            query = sql.SQL("SELECT count(*) FROM public.{}").format(
                sql.Identifier(table)
            )
            return int(connection.execute(query).fetchone()[0])

    @staticmethod
    def _adapt(value: Any, data_type: str) -> Any:
        if value is None:
            return None
        if data_type in {"json", "jsonb"}:
            return Jsonb(value)
        return value

    def upsert_batch(
        self,
        table: str,
        primary_key: str,
        rows: Sequence[Mapping[str, Any]],
        column_types: Mapping[str, str],
    ) -> None:
        if not rows:
            return
        table = _safe_ident(table)
        primary_key = _safe_ident(primary_key)
        names = list(rows[0])
        for name in names:
            _safe_ident(name)
        if primary_key not in names:
            raise RuntimeError(f"{table}: primary key missing from source rows")
        expected = set(names)
        for row in rows:
            if set(row) != expected:
                raise RuntimeError(f"{table}: inconsistent source row shape")
        unknown = sorted(expected - set(column_types))
        if unknown:
            raise RuntimeError(f"{table}: target missing source columns {unknown}")
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in names)
        insert_columns = sql.SQL(", ").join(sql.Identifier(name) for name in names)
        updates = [
            sql.SQL("{} = EXCLUDED.{}").format(
                sql.Identifier(name),
                sql.Identifier(name),
            )
            for name in names
            if name != primary_key
        ]
        if updates:
            conflict = sql.SQL("DO UPDATE SET {}").format(sql.SQL(", ").join(updates))
        else:
            conflict = sql.SQL("DO NOTHING")
        statement = sql.SQL(
            "INSERT INTO public.{} ({}) VALUES ({}) "
            "ON CONFLICT ({}) {}"
        ).format(
            sql.Identifier(table),
            insert_columns,
            placeholders,
            sql.Identifier(primary_key),
            conflict,
        )

        with self._connect() as connection:
            with connection.transaction():
                for row in rows:
                    params = [
                        self._adapt(row[name], column_types[name])
                        for name in names
                    ]
                    connection.execute(statement, params)

    def rows_by_primary_keys(
        self,
        table: str,
        primary_key: str,
        keys: Sequence[object],
        columns: Sequence[str],
    ) -> list[dict[str, Any]]:
        if not keys:
            return []
        table = _safe_ident(table)
        primary_key = _safe_ident(primary_key)
        for name in columns:
            _safe_ident(name)
        select_columns = sql.SQL(", ").join(sql.Identifier(name) for name in columns)
        statement = sql.SQL(
            "SELECT {} FROM public.{} "
            "WHERE {} = ANY(%s) ORDER BY {} ASC"
        ).format(
            select_columns,
            sql.Identifier(table),
            sql.Identifier(primary_key),
            sql.Identifier(primary_key),
        )
        with self._connect() as connection:
            cursor = connection.execute(statement, (list(keys),))
            names = [item.name for item in cursor.description or ()]
            return [
                dict(zip(names, row, strict=True))
                for row in cursor.fetchall()
            ]

    def all_primary_keys(
        self,
        table: str,
        primary_key: str,
    ) -> list[object]:
        table = _safe_ident(table)
        primary_key = _safe_ident(primary_key)
        statement = sql.SQL(
            "SELECT {} FROM public.{} ORDER BY {} ASC"
        ).format(
            sql.Identifier(primary_key),
            sql.Identifier(table),
            sql.Identifier(primary_key),
        )
        with self._connect() as connection:
            return [
                row[0]
                for row in connection.execute(statement).fetchall()
            ]


def _source_pk_digest(
    source: RestShadowSource,
    item: ShadowTable,
    *,
    batch_size: int,
) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    for batch in source.all_rows(
        item.name,
        item.primary_key,
        limit=batch_size,
        columns=(item.primary_key,),
    ):
        for row in batch:
            digest.update(str(row[item.primary_key]).encode("utf-8"))
            digest.update(b"\n")
            count += 1
    return count, digest.hexdigest()


def _target_pk_digest(
    target: EmpireDbShadowTarget,
    item: ShadowTable,
) -> tuple[int, str]:
    keys = target.all_primary_keys(item.name, item.primary_key)
    digest = hashlib.sha256()
    for value in keys:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return len(keys), digest.hexdigest()


def copy_table(
    source: RestShadowSource,
    target: EmpireDbShadowTarget,
    item: ShadowTable,
    *,
    batch_size: int,
) -> dict[str, Any]:
    target_columns = target.columns(item.name)
    column_types = dict(target_columns)
    target_column_names = [name for name, _ in target_columns]
    source_count_before = source.exact_count(item.name, item.primary_key)
    copied = 0
    batches = 0
    source_columns: list[str] | None = None

    for batch in source.all_rows(
        item.name,
        item.primary_key,
        limit=batch_size,
    ):
        if source_columns is None:
            source_columns = list(batch[0])
            missing_target = sorted(set(source_columns) - set(target_column_names))
            if missing_target:
                raise RuntimeError(
                    f"{item.name}: target missing columns {missing_target}"
                )
        target.upsert_batch(
            item.name,
            item.primary_key,
            batch,
            column_types,
        )
        keys = [row[item.primary_key] for row in batch]
        echoed = target.rows_by_primary_keys(
            item.name,
            item.primary_key,
            keys,
            source_columns,
        )
        expected = sorted(batch, key=lambda row: str(row[item.primary_key]))
        actual = sorted(echoed, key=lambda row: str(row[item.primary_key]))
        if digest_rows(expected) != digest_rows(actual):
            raise RuntimeError(
                f"{item.name}: semantic round-trip verification failed"
            )
        copied += len(batch)
        batches += 1

    target_count = target.exact_count(item.name)
    source_count_after = source.exact_count(item.name, item.primary_key)
    source_pk_count, source_pk_sha256 = _source_pk_digest(
        source,
        item,
        batch_size=batch_size,
    )
    target_pk_count, target_pk_sha256 = _target_pk_digest(target, item)
    verified = (
        source_count_after == target_count
        and source_pk_count == target_pk_count
        and source_pk_sha256 == target_pk_sha256
    )
    return {
        "table": item.name,
        "source_count_before": source_count_before,
        "source_count_after": source_count_after,
        "target_count": target_count,
        "rows_seen": copied,
        "batches": batches,
        "source_pk_sha256": source_pk_sha256,
        "target_pk_sha256": target_pk_sha256,
        "verified": verified,
    }


def plan(
    source: RestShadowSource,
    target: EmpireDbShadowTarget,
    tables: Sequence[ShadowTable],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in tables:
        target_columns = target.columns(item.name)
        rows.append(
            {
                "table": item.name,
                "primary_key": item.primary_key,
                "parents": list(item.parents),
                "source_count": source.exact_count(item.name, item.primary_key),
                "target_count": target.exact_count(item.name),
                "target_columns": len(target_columns),
            }
        )
    return {
        "schema_version": "empire.shadow-copy-plan.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_truncate_authority": False,
        "production_cutover_authority": False,
        "tables": rows,
    }


def run_copy(
    source: RestShadowSource,
    target: EmpireDbShadowTarget,
    tables: Sequence[ShadowTable],
    *,
    batch_size: int,
    passes: int,
) -> dict[str, Any]:
    pass_results: list[dict[str, Any]] = []
    for pass_number in range(1, passes + 1):
        results: list[dict[str, Any]] = []
        all_verified = True
        for item in tables:
            result = copy_table(
                source,
                target,
                item,
                batch_size=batch_size,
            )
            results.append(result)
            all_verified = all_verified and bool(result["verified"])
            print(json.dumps(result, sort_keys=True), flush=True)
        pass_results.append(
            {
                "pass": pass_number,
                "verified": all_verified,
                "tables": results,
            }
        )
        if all_verified:
            break

    verified = bool(pass_results) and bool(pass_results[-1]["verified"])
    report = {
        "schema_version": "empire.shadow-copy-report.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_truncate_authority": False,
        "production_cutover_authority": False,
        "verified": verified,
        "passes": pass_results,
    }
    if not verified:
        raise RuntimeError(
            "shadow copy did not converge to exact count + primary-key parity"
        )
    return report


def _source_from_env() -> RestShadowSource:
    api_url = os.getenv("EMPIRE_SHADOW_SOURCE_API_URL", "").strip()
    api_key = os.getenv("EMPIRE_SHADOW_SOURCE_TOKEN", "").strip()
    if not api_url or not api_key:
        raise RuntimeError(
            "EMPIRE_SHADOW_SOURCE_API_URL and EMPIRE_SHADOW_SOURCE_TOKEN are required"
        )
    return RestShadowSource(api_url, api_key)


def _target_from_env() -> EmpireDbShadowTarget:
    dsn = os.getenv("EMPIREDB_MIGRATOR_DSN", "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_MIGRATOR_DSN is required")
    return EmpireDbShadowTarget(dsn)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Governed shadow copy into EmpireDB"
    )
    parser.add_argument(
        "--mode",
        choices=("plan", "copy"),
        default="plan",
    )
    parser.add_argument(
        "--tables",
        default="",
        help="comma-separated requested tables; dependencies are auto-included",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--report-path",
        default="runtime/data_cloud/shadow_copy_latest.json",
    )
    args = parser.parse_args(argv)

    batch_size = max(1, min(int(args.batch_size), 1000))
    passes = max(1, min(int(args.passes), 5))
    names = [part.strip() for part in args.tables.split(",") if part.strip()]
    tables = resolve_tables(names or None)
    source = _source_from_env()
    target = _target_from_env()

    if args.mode == "plan":
        report = plan(source, target, tables)
    else:
        report = run_copy(
            source,
            target,
            tables,
            batch_size=batch_size,
            passes=passes,
        )

    path = args.report_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
