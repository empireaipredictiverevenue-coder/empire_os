"""Least-privilege PostgreSQL transport for Lead Intelligence."""
from __future__ import annotations

import os
from typing import Any, Callable


class LeadIntelligenceTransportError(RuntimeError):
    """Dedicated Lead Intelligence transport is unavailable or unsafe."""


ROLE = "empire_lead_intelligence_reader"


def _eq_uuid(value: str, *, field: str) -> str:
    prefix = "eq."
    raw = str(value or "")
    if not raw.startswith(prefix):
        raise LeadIntelligenceTransportError(
            f"{field} must use eq. UUID filter"
        )
    from uuid import UUID

    try:
        return str(UUID(raw[len(prefix):]))
    except (TypeError, ValueError, AttributeError) as exc:
        raise LeadIntelligenceTransportError(
            f"invalid {field} UUID filter"
        ) from exc


def _limit(value: str, *, maximum: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LeadIntelligenceTransportError(
            "invalid lead intelligence limit"
        ) from exc
    if not 1 <= parsed <= maximum:
        raise LeadIntelligenceTransportError(
            "lead intelligence limit out of range"
        )
    return parsed


class PostgresLeadIntelligenceReader:
    """Translate the projection's fixed read contract into static SQL."""

    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise LeadIntelligenceTransportError(
                "EMPIRE_LEAD_INTELLIGENCE_DSN is required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise LeadIntelligenceTransportError(
                    "psycopg is required for Lead Intelligence transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    @classmethod
    def from_env(cls) -> "PostgresLeadIntelligenceReader":
        return cls(
            os.getenv("EMPIRE_LEAD_INTELLIGENCE_DSN", "")
        )

    def __call__(
        self,
        path: str,
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        sql, values = self._compile(path, params)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(sql, values)
                    columns = [
                        description.name
                        for description in cursor.description
                    ]
                    rows = cursor.fetchall()
        except Exception as exc:
            raise LeadIntelligenceTransportError(
                "dedicated Lead Intelligence database read failed"
            ) from exc

        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]

    def _compile(
        self,
        path: str,
        params: dict[str, str],
    ) -> tuple[str, tuple[Any, ...]]:
        if not isinstance(params, dict):
            raise LeadIntelligenceTransportError(
                "Lead Intelligence parameters must be a mapping"
            )

        select = str(params.get("select") or "").strip()
        if not select:
            raise LeadIntelligenceTransportError(
                "Lead Intelligence select list required"
            )

        if path == "/rest/v1/prospects":
            self._expect_keys(
                params,
                {"select", "id", "limit"},
            )
            prospect_id = _eq_uuid(
                params["id"],
                field="prospect id",
            )
            limit = _limit(params["limit"], maximum=1)
            sql = (
                "SELECT " + self._safe_select(select, {
                    "id","created_at","business_name","niche","metro",
                    "phone","website","address","rating","review_count",
                    "buy_signal_score","runs_ads","status","notes",
                    "contacted_at","contact_name","contact_title",
                    "contact_source","contacted_status",
                })
                + " FROM public.prospects WHERE id=%s LIMIT %s"
            )
            return sql, (prospect_id, limit)

        if path == "/rest/v1/prospect_entity_links":
            self._expect_keys(
                params,
                {"select", "prospect_id", "active", "limit"},
            )
            if params["active"] != "eq.true":
                raise LeadIntelligenceTransportError(
                    "identity link query must require active=true"
                )
            prospect_id = _eq_uuid(
                params["prospect_id"],
                field="prospect id",
            )
            limit = _limit(params["limit"], maximum=2)
            sql = (
                "SELECT " + self._safe_select(select, {
                    "prospect_id","entity_id","match_method",
                    "match_score","evidence","active","created_at",
                })
                + " FROM public.prospect_entity_links "
                "WHERE prospect_id=%s AND active=true "
                "ORDER BY created_at DESC LIMIT %s"
            )
            return sql, (prospect_id, limit)

        if path == "/rest/v1/business_entities":
            self._expect_keys(
                params,
                {"select", "id", "limit"},
            )
            entity_id = _eq_uuid(
                params["id"],
                field="entity id",
            )
            limit = _limit(params["limit"], maximum=1)
            sql = (
                "SELECT " + self._safe_select(select, {
                    "id","canonical_name","normalized_name",
                    "canonical_niche","canonical_metro",
                    "canonical_phone","canonical_website",
                    "identity_confidence","resolution_state",
                    "provenance","created_at","updated_at",
                })
                + " FROM public.business_entities WHERE id=%s LIMIT %s"
            )
            return sql, (entity_id, limit)

        if path == "/rest/v1/prospect_qualifications":
            self._expect_keys(
                params,
                {
                    "select","prospect_id","scoring_engine",
                    "scoring_version","order","limit",
                },
            )
            if params["scoring_engine"] != "eq.empire_os.lead_scoring":
                raise LeadIntelligenceTransportError(
                    "unexpected qualification scoring engine"
                )
            if params["scoring_version"] != "eq.v1":
                raise LeadIntelligenceTransportError(
                    "unexpected qualification scoring version"
                )
            if params["order"] != "scored_at.desc":
                raise LeadIntelligenceTransportError(
                    "qualification ordering must be scored_at.desc"
                )
            prospect_id = _eq_uuid(
                params["prospect_id"],
                field="prospect id",
            )
            limit = _limit(params["limit"], maximum=1)
            sql = (
                "SELECT " + self._safe_select(select, {
                    "id","prospect_id","score","tier","status",
                    "recommended_action","scoring_engine",
                    "scoring_version","input_snapshot","result_payload",
                    "scored_at","updated_at",
                })
                + " FROM public.prospect_qualifications "
                "WHERE prospect_id=%s "
                "AND scoring_engine='empire_os.lead_scoring' "
                "AND scoring_version='v1' "
                "ORDER BY scored_at DESC LIMIT %s"
            )
            return sql, (prospect_id, limit)

        entity_tables = {
            "/rest/v1/intelligence_facts": (
                "public.intelligence_facts",
                {
                    "id","entity_type","entity_id","fact_key","fact_value",
                    "source_id","confidence","first_seen_at","last_seen_at",
                    "valid_from","valid_to","evidence_uri","evidence_hash",
                    "created_at",
                },
                "last_seen_at.desc",
                "last_seen_at DESC",
            ),
            "/rest/v1/intelligence_signals": (
                "public.intelligence_signals",
                {
                    "id","entity_id","signal_type","signal_domain",
                    "observed_at","source_id","strength","confidence",
                    "expires_at","payload","created_at",
                },
                "observed_at.desc",
                "observed_at DESC",
            ),
            "/rest/v1/intelligence_scores": (
                "public.intelligence_scores",
                {
                    "id","entity_type","entity_id","score_type","score",
                    "confidence","model_key","features","explanation",
                    "scored_at",
                },
                "scored_at.desc",
                "scored_at DESC",
            ),
            "/rest/v1/intelligence_contact_points": (
                "public.intelligence_contact_points",
                {
                    "id","person_id","entity_id","contact_type","value",
                    "normalized_value","verification_state","source_id",
                    "first_seen_at","last_seen_at","verified_at",
                    "confidence",
                },
                "last_seen_at.desc",
                "last_seen_at DESC",
            ),
            "/rest/v1/intelligence_employment": (
                "public.intelligence_employment",
                {
                    "id","person_id","entity_id","title",
                    "normalized_title","seniority","department",
                    "buying_role","is_current","valid_from","valid_to",
                    "confidence","created_at",
                },
                "created_at.desc",
                "created_at DESC",
            ),
        }
        if path in entity_tables:
            self._expect_keys(
                params,
                {"select", "entity_id", "order", "limit"},
            )
            table, allowed, expected_order, sql_order = entity_tables[path]
            if params["order"] != expected_order:
                raise LeadIntelligenceTransportError(
                    "unexpected entity intelligence ordering"
                )
            entity_id = _eq_uuid(
                params["entity_id"],
                field="entity id",
            )
            limit = _limit(params["limit"])
            sql = (
                "SELECT " + self._safe_select(select, allowed)
                + f" FROM {table} WHERE entity_id=%s "
                + f"ORDER BY {sql_order} LIMIT %s"
            )
            return sql, (entity_id, limit)

        raise LeadIntelligenceTransportError(
            "unsupported Lead Intelligence read path"
        )

    @staticmethod
    def _expect_keys(
        params: dict[str, str],
        expected: set[str],
    ) -> None:
        if set(params) != expected:
            raise LeadIntelligenceTransportError(
                "unexpected Lead Intelligence query parameters"
            )

    @staticmethod
    def _safe_select(
        select: str,
        allowed: set[str],
    ) -> str:
        columns = [
            column.strip()
            for column in select.split(",")
            if column.strip()
        ]
        if (
            not columns
            or len(columns) != len(set(columns))
            or any(column not in allowed for column in columns)
        ):
            raise LeadIntelligenceTransportError(
                "unsafe Lead Intelligence select list"
            )
        return ",".join(columns)
